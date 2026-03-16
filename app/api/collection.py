"""
Collection and Favorites API Routes
User's personal ant collection and favorites management
"""
from typing import Annotated
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.cloud.firestore import Client, Query as FirestoreQuery, ArrayRemove
from firebase_admin import firestore

from app.models.collection import (
    CollectionItemCreate,
    CollectionItemSchema,
    CollectionListResponse,
    FolderCreate,
    FolderUpdate,
    FolderSchema,
    FolderListResponse,
    AddToFoldersRequest,
)
from app.dependencies.auth import get_current_user

router = APIRouter()
db: Client = firestore.client()

USERS_COLLECTION = "users"
COLLECTION_SUBCOLLECTION = "collection"
FOLDERS_SUBCOLLECTION = "folders"
SPECIES_COLLECTION = "species"
COLLECTION_ITEM_LABEL = "Collection item"
APP_JSON = "application/json"


_R500 = {
    500: {"description": "Internal Server Error",
          "content": {APP_JSON: {"example": {"detail": "An unexpected error occurred."}}}},
}
_R404_500 = {
    404: {"description": "Resource not found",
          "content": {APP_JSON: {"example": {"detail": "<Resource> not found"}}}},
    **_R500,
}
_R400_404_500 = {
    400: {"description": "Bad request",
          "content": {APP_JSON: {"example": {"detail": "Invalid request."}}}},
    **_R404_500,
}


def _now_utc() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=timezone.utc)


def _user_collection_ref(user_id: str) -> FirestoreQuery:
    """Reference to a user's collection subcollection."""
    return (
        db.collection(USERS_COLLECTION)
        .document(user_id)
        .collection(COLLECTION_SUBCOLLECTION)
    )


def _user_folders_ref(user_id: str) -> FirestoreQuery:
    """Reference to a user's folders subcollection."""
    return (
        db.collection(USERS_COLLECTION)
        .document(user_id)
        .collection(FOLDERS_SUBCOLLECTION)
    )


def _get_doc_or_404(ref, label: str):
    """Fetch a Firestore document reference or raise HTTP 404."""
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return doc


def _verify_folders_exist(user_id: str, folder_ids: list[str]) -> None:
    """Raise HTTP 404 if any of the given folder IDs do not exist for this user."""
    for folder_id in folder_ids:
        folder_ref = _user_folders_ref(user_id).document(folder_id)
        if not folder_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Folder {folder_id} not found")


def _get_species_details(species_id: str) -> dict:
    """Fetch species details for enriching collection items. Returns {} on miss or error."""
    try:
        doc = db.collection(SPECIES_COLLECTION).document(species_id).get()
        if doc.exists:
            data = doc.to_dict()
            return {
                "species_name": data.get("name"),
                "species_scientific_name": data.get("scientific_name"),
                "species_image": data.get("image"),
                "species_about": data.get("about"),
            }
    except (GoogleAPICallError, RetryError, ValueError, TypeError):
        pass
    return {}


@router.get("/users/me/collection", response_model=CollectionListResponse, responses=_R500)
async def get_my_collection(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current user's ant collection."""
    try:
        user_id = current_user["uid"]
        docs = (
            _user_collection_ref(user_id)
            .order_by("added_at", direction=FirestoreQuery.DESCENDING)
            .stream()
        )

        items = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            data.setdefault("folder_ids", [])
            data.update(_get_species_details(data.get("species_id", "")))
            items.append(data)

        return CollectionListResponse(items=items, total=len(items))
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/users/me/collection",
    response_model=CollectionItemSchema,
    responses=_R400_404_500,
)
async def add_to_collection(
    item: CollectionItemCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a species to user's collection."""
    try:
        user_id = current_user["uid"]

        species_ref = db.collection(SPECIES_COLLECTION).document(item.species_id)
        _get_doc_or_404(species_ref, "Species")

        existing = (
            _user_collection_ref(user_id)
            .where("species_id", "==", item.species_id)
            .limit(1)
            .stream()
        )
        if any(True for _ in existing):
            raise HTTPException(status_code=400, detail="Species already in collection")

        item_id = str(uuid.uuid4())
        item_data = {**item.model_dump(), "added_at": _now_utc()}
        _user_collection_ref(user_id).document(item_id).set(item_data)

        item_data["id"] = item_id
        item_data["user_id"] = user_id
        item_data.update(_get_species_details(item.species_id))

        return item_data
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/collection/{item_id}", responses=_R404_500)
async def remove_from_collection(
    item_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Remove a species from user's collection."""
    try:
        user_id = current_user["uid"]
        doc_ref = _user_collection_ref(user_id).document(item_id)
        _get_doc_or_404(doc_ref, COLLECTION_ITEM_LABEL)
        doc_ref.delete()
        return {"message": "Item removed from collection"}
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/users/me/folders", response_model=FolderListResponse, responses=_R500)
async def get_my_folders(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current user's folders with item counts."""
    try:
        user_id = current_user["uid"]

        folder_docs = (
            _user_folders_ref(user_id)
            .order_by("created_at", direction=FirestoreQuery.DESCENDING)
            .stream()
        )

        # Count items per folder in a single pass
        folder_item_counts: dict[str, int] = {}
        for col_doc in _user_collection_ref(user_id).stream():
            for fid in col_doc.to_dict().get("folder_ids", []):
                folder_item_counts[fid] = folder_item_counts.get(fid, 0) + 1

        folders = []
        for doc in folder_docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            data["item_count"] = folder_item_counts.get(doc.id, 0)
            folders.append(data)

        return FolderListResponse(folders=folders, total=len(folders))
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/users/me/folders",
    response_model=FolderSchema,
    responses=_R400_404_500,
)
async def create_folder(
    folder: FolderCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new folder."""
    try:
        user_id = current_user["uid"]

        existing = (
            _user_folders_ref(user_id)
            .where("name", "==", folder.name)
            .limit(1)
            .stream()
        )
        if any(True for _ in existing):
            raise HTTPException(status_code=400, detail="Folder with this name already exists")

        folder_id = str(uuid.uuid4())
        now = _now_utc()
        folder_data = {**folder.model_dump(), "created_at": now, "updated_at": now}
        _user_folders_ref(user_id).document(folder_id).set(folder_data)

        return {**folder_data, "id": folder_id, "user_id": user_id, "item_count": 0}
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put(
    "/users/me/folders/{folder_id}",
    response_model=FolderSchema,
    responses=_R400_404_500,
)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a folder."""
    try:
        user_id = current_user["uid"]
        doc_ref = _user_folders_ref(user_id).document(folder_id)
        _get_doc_or_404(doc_ref, "Folder")

        update_data = {k: v for k, v in folder_update.model_dump().items() if v is not None}

        if "name" in update_data:
            existing = list(
                _user_folders_ref(user_id)
                .where("name", "==", update_data["name"])
                .limit(1)
                .stream()
            )
            if existing and existing[0].id != folder_id:
                raise HTTPException(status_code=400, detail="Folder with this name already exists")

        update_data["updated_at"] = _now_utc()
        doc_ref.update(update_data)

        folder_data = doc_ref.get().to_dict()
        folder_data["id"] = folder_id
        folder_data["user_id"] = user_id
        folder_data["item_count"] = sum(
            1 for _ in
            _user_collection_ref(user_id)
            .where("folder_ids", "array_contains", folder_id)
            .stream()
        )

        return folder_data
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/folders/{folder_id}", responses=_R404_500)
async def delete_folder(
    folder_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    delete_items: Annotated[bool,
                            Query(
                                description="Also delete collection items in this folder"
                                )] = False,
):
    """Delete a folder. Optionally delete items in the folder."""
    try:
        user_id = current_user["uid"]
        doc_ref = _user_folders_ref(user_id).document(folder_id)
        _get_doc_or_404(doc_ref, "Folder")

        items_in_folder = list(
            _user_collection_ref(user_id)
            .where("folder_ids", "array_contains", folder_id)
            .stream()
        )

        for item_doc in items_in_folder:
            if delete_items:
                item_doc.reference.delete()
            else:
                item_doc.reference.update({"folder_ids": ArrayRemove([folder_id])})

        doc_ref.delete()

        return {
            "message": "Folder deleted",
            "items_affected": len(items_in_folder),
            "items_deleted": delete_items,
        }
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/users/me/collection/{item_id}/folders", responses=_R404_500)
async def add_item_to_folders(
    item_id: str,
    request: AddToFoldersRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a collection item to one or more folders."""
    try:
        user_id = current_user["uid"]
        item_ref = _user_collection_ref(user_id).document(item_id)
        item_doc = _get_doc_or_404(item_ref, COLLECTION_ITEM_LABEL)

        _verify_folders_exist(user_id, request.folder_ids)

        new_folder_ids = list(
            set(item_doc.to_dict().get("folder_ids", [])) | set(request.folder_ids)
        )
        item_ref.update({"folder_ids": new_folder_ids})

        return {"message": "Item added to folders", "folder_ids": new_folder_ids}
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/collection/{item_id}/folders/{folder_id}", responses=_R400_404_500)
async def remove_item_from_folder(
    item_id: str,
    folder_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Remove a collection item from a folder."""
    try:
        user_id = current_user["uid"]
        item_ref = _user_collection_ref(user_id).document(item_id)
        item_doc = _get_doc_or_404(item_ref, COLLECTION_ITEM_LABEL)

        folder_ids: list[str] = item_doc.to_dict().get("folder_ids", [])
        if folder_id not in folder_ids:
            raise HTTPException(status_code=400, detail="Item is not in this folder")

        item_ref.update({"folder_ids": ArrayRemove([folder_id])})
        folder_ids.remove(folder_id)

        return {"message": "Item removed from folder", "folder_ids": folder_ids}
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/users/me/collection/{item_id}/folders", responses=_R404_500)
async def set_item_folders(
    item_id: str,
    request: AddToFoldersRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Set the folders for a collection item (replaces existing folder assignments)."""
    try:
        user_id = current_user["uid"]
        item_ref = _user_collection_ref(user_id).document(item_id)
        _get_doc_or_404(item_ref, COLLECTION_ITEM_LABEL)

        _verify_folders_exist(user_id, request.folder_ids)
        item_ref.update({"folder_ids": request.folder_ids})

        return {"message": "Item folders updated", "folder_ids": request.folder_ids}
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/users/me/collection/{species_id}/check", responses=_R500)
async def check_if_in_collection(
    species_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Check if a species is in user's collection."""
    try:
        user_id = current_user["uid"]
        items = list(
            _user_collection_ref(user_id)
            .where("species_id", "==", species_id)
            .limit(1)
            .stream()
        )
        in_collection = bool(items)
        return {
            "in_collection": in_collection,
            "collection_id": items[0].id if in_collection else None,
        }
    except (GoogleAPICallError, RetryError, ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
