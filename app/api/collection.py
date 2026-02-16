"""
Collection and Favorites API Routes
User's personal ant collection and favorites management
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime
import uuid

from firebase_admin import firestore
from app.models.collection import (
    CollectionItemCreate,
    CollectionItemSchema,
    CollectionListResponse,
    FavoriteItemCreate,
    FavoriteItemSchema,
    FavoriteListResponse,
    FolderCreate,
    FolderUpdate,
    FolderSchema,
    FolderListResponse,
    AddToFoldersRequest,
    # News favorites models
    FavoriteNewsCreate,
    FavoriteNewsSchema,
    FavoriteNewsListResponse,
    CheckFavoriteNewsResponse,
)
from app.dependencies.auth import get_current_user

router = APIRouter()
db = firestore.client()

USERS_COLLECTION = "users"
COLLECTION_SUBCOLLECTION = "collection"
FAVORITES_SUBCOLLECTION = "favorites"
FAVORITES_NEWS_SUBCOLLECTION = "favorites_news"
FOLDERS_SUBCOLLECTION = "folders"
SPECIES_COLLECTION = "species"
NEWS_COLLECTION = "news"


async def get_species_details(species_id: str) -> dict:
    """Fetch species details for enriching collection/favorite items"""
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
    except Exception:
        pass
    return {}


async def get_news_details(news_id: str) -> dict:
    """Fetch news details for enriching favorite news items"""
    try:
        doc = db.collection(NEWS_COLLECTION).document(news_id).get()
        if doc.exists:
            data = doc.to_dict()
            return {
                "news_title": data.get("title"),
                "news_description": data.get("description"),
                "news_link": data.get("link"),
                "news_image": data.get("image"),
                "news_source": data.get("source"),
                "news_published_at": data.get("published_at"),
            }
    except Exception:
        pass
    return {}


# COLLECTION ENDPOINTS

@router.get("/users/me/collection", response_model=CollectionListResponse)
async def get_my_collection(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's ant collection"""
    try:
        user_id = current_user["uid"]
        collection_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
        )
        
        docs = collection_ref.order_by("added_at", direction=firestore.Query.DESCENDING).stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            # Ensure folder_ids is present (for backwards compatibility)
            if "folder_ids" not in data:
                data["folder_ids"] = []

            # Enrich with species details
            species_details = await get_species_details(data.get("species_id", ""))
            data.update(species_details)

            items.append(data)

        return CollectionListResponse(items=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/me/collection", response_model=CollectionItemSchema)
async def add_to_collection(
    item: CollectionItemCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a species to user's collection"""
    try:
        user_id = current_user["uid"]

        # Verify species exists
        species_doc = db.collection(SPECIES_COLLECTION).document(item.species_id).get()
        if not species_doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")

        # Check if already in collection
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .where("species_id", "==", item.species_id)
            .limit(1)
            .stream()
        )
        if len(list(existing)) > 0:
            raise HTTPException(status_code=400, detail="Species already in collection")

        # Create collection item
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()

        item_data = item.model_dump()
        item_data["added_at"] = now

        (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .document(item_id)
            .set(item_data)
        )

        # Return with species details
        item_data["id"] = item_id
        item_data["user_id"] = user_id
        species_details = await get_species_details(item.species_id)
        item_data.update(species_details)

        return item_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/me/collection/{item_id}")
async def remove_from_collection(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a species from user's collection"""
    try:
        user_id = current_user["uid"]

        doc_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .document(item_id)
        )

        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Collection item not found")

        doc_ref.delete()

        return {"message": "Item removed from collection"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# FOLDER ENDPOINTS

@router.get("/users/me/folders", response_model=FolderListResponse)
async def get_my_folders(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's folders with item counts"""
    try:
        user_id = current_user["uid"]
        folders_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FOLDERS_SUBCOLLECTION)
        )

        docs = folders_ref.order_by("created_at", direction=firestore.Query.DESCENDING).stream()

        # Get all collection items to count items per folder
        collection_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
        )
        collection_docs = list(collection_ref.stream())

        # Count items per folder
        folder_item_counts = {}
        for col_doc in collection_docs:
            col_data = col_doc.to_dict()
            folder_ids = col_data.get("folder_ids", [])
            for folder_id in folder_ids:
                folder_item_counts[folder_id] = folder_item_counts.get(folder_id, 0) + 1

        folders = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            data["item_count"] = folder_item_counts.get(doc.id, 0)
            folders.append(data)

        return FolderListResponse(folders=folders, total=len(folders))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/me/folders", response_model=FolderSchema)
async def create_folder(
    folder: FolderCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new folder"""
    try:
        user_id = current_user["uid"]

        # Check if folder with same name already exists
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FOLDERS_SUBCOLLECTION)
            .where("name", "==", folder.name)
            .limit(1)
            .stream()
        )
        if len(list(existing)) > 0:
            raise HTTPException(status_code=400, detail="Folder with this name already exists")

        # Create folder
        folder_id = str(uuid.uuid4())
        now = datetime.utcnow()

        folder_data = folder.model_dump()
        folder_data["created_at"] = now
        folder_data["updated_at"] = now

        (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FOLDERS_SUBCOLLECTION)
            .document(folder_id)
            .set(folder_data)
        )

        folder_data["id"] = folder_id
        folder_data["user_id"] = user_id
        folder_data["item_count"] = 0

        return folder_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/me/folders/{folder_id}", response_model=FolderSchema)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a folder"""
    try:
        user_id = current_user["uid"]

        doc_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FOLDERS_SUBCOLLECTION)
            .document(folder_id)
        )

        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Check if new name conflicts with existing folder
        update_data = {k: v for k, v in folder_update.model_dump().items() if v is not None}

        if "name" in update_data:
            existing = (
                db.collection(USERS_COLLECTION)
                .document(user_id)
                .collection(FOLDERS_SUBCOLLECTION)
                .where("name", "==", update_data["name"])
                .limit(1)
                .stream()
            )
            existing_list = list(existing)
            if len(existing_list) > 0 and existing_list[0].id != folder_id:
                raise HTTPException(status_code=400, detail="Folder with this name already exists")

        update_data["updated_at"] = datetime.utcnow()
        doc_ref.update(update_data)

        # Get updated document
        updated_doc = doc_ref.get()
        folder_data = updated_doc.to_dict()
        folder_data["id"] = folder_id
        folder_data["user_id"] = user_id

        # Count items in this folder
        collection_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .where("folder_ids", "array_contains", folder_id)
        )
        folder_data["item_count"] = len(list(collection_ref.stream()))

        return folder_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/me/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    delete_items: bool = Query(False, description="If true, also delete collection items in this folder"),
    current_user: dict = Depends(get_current_user),
):
    """Delete a folder. Optionally delete items in the folder."""
    try:
        user_id = current_user["uid"]
        
        doc_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FOLDERS_SUBCOLLECTION)
            .document(folder_id)
        )
        
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Get items in this folder
        collection_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .where("folder_ids", "array_contains", folder_id)
        )
        items_in_folder = list(collection_ref.stream())
        
        if delete_items:
            # Delete all items in the folder
            for item_doc in items_in_folder:
                item_doc.reference.delete()
        else:
            # Remove folder_id from items' folder_ids array
            for item_doc in items_in_folder:
                item_data = item_doc.to_dict()
                folder_ids = item_data.get("folder_ids", [])
                if folder_id in folder_ids:
                    folder_ids.remove(folder_id)
                    item_doc.reference.update({"folder_ids": folder_ids})
        
        # Delete the folder
        doc_ref.delete()
        
        return {
            "message": "Folder deleted",
            "items_affected": len(items_in_folder),
            "items_deleted": delete_items
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# FOLDER ASSIGNMENT ENDPOINTS

@router.post("/users/me/collection/{item_id}/folders")
async def add_item_to_folders(
    item_id: str,
    request: AddToFoldersRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a collection item to one or more folders"""
    try:
        user_id = current_user["uid"]
        
        # Get the collection item
        item_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .document(item_id)
        )
        
        item_doc = item_ref.get()
        if not item_doc.exists:
            raise HTTPException(status_code=404, detail="Collection item not found")
        
        # Verify all folders exist
        for folder_id in request.folder_ids:
            folder_ref = (
                db.collection(USERS_COLLECTION)
                .document(user_id)
                .collection(FOLDERS_SUBCOLLECTION)
                .document(folder_id)
            )
            if not folder_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Folder {folder_id} not found")
        
        # Update item's folder_ids
        item_data = item_doc.to_dict()
        current_folder_ids = set(item_data.get("folder_ids", []))
        current_folder_ids.update(request.folder_ids)
        
        item_ref.update({"folder_ids": list(current_folder_ids)})
        
        return {"message": "Item added to folders", "folder_ids": list(current_folder_ids)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/me/collection/{item_id}/folders/{folder_id}")
async def remove_item_from_folder(
    item_id: str,
    folder_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a collection item from a folder"""
    try:
        user_id = current_user["uid"]
        
        # Get the collection item
        item_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .document(item_id)
        )
        
        item_doc = item_ref.get()
        if not item_doc.exists:
            raise HTTPException(status_code=404, detail="Collection item not found")
        
        # Update item's folder_ids
        item_data = item_doc.to_dict()
        folder_ids = item_data.get("folder_ids", [])
        
        if folder_id not in folder_ids:
            raise HTTPException(status_code=400, detail="Item is not in this folder")
        
        folder_ids.remove(folder_id)
        item_ref.update({"folder_ids": folder_ids})
        
        return {"message": "Item removed from folder", "folder_ids": folder_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/me/collection/{item_id}/folders")
async def set_item_folders(
    item_id: str,
    request: AddToFoldersRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set the folders for a collection item (replaces existing folder assignments)"""
    try:
        user_id = current_user["uid"]
        
        # Get the collection item
        item_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .document(item_id)
        )
        
        item_doc = item_ref.get()
        if not item_doc.exists:
            raise HTTPException(status_code=404, detail="Collection item not found")
        
        # Verify all folders exist
        for folder_id in request.folder_ids:
            folder_ref = (
                db.collection(USERS_COLLECTION)
                .document(user_id)
                .collection(FOLDERS_SUBCOLLECTION)
                .document(folder_id)
            )
            if not folder_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Folder {folder_id} not found")
        
        # Set item's folder_ids
        item_ref.update({"folder_ids": request.folder_ids})
        
        return {"message": "Item folders updated", "folder_ids": request.folder_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# SPECIES FAVORITES ENDPOINTS

@router.get("/users/me/favorites", response_model=FavoriteListResponse)
async def get_my_favorites(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's favorite species"""
    try:
        user_id = current_user["uid"]
        favorites_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_SUBCOLLECTION)
        )
        
        docs = favorites_ref.order_by("added_at", direction=firestore.Query.DESCENDING).stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            
            # Enrich with species details
            species_details = await get_species_details(data.get("species_id", ""))
            data.update(species_details)
            
            items.append(data)
        
        return FavoriteListResponse(items=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/me/favorites", response_model=FavoriteItemSchema)
async def add_to_favorites(
    item: FavoriteItemCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a species to user's favorites"""
    try:
        user_id = current_user["uid"]
        
        # Verify species exists
        species_doc = db.collection(SPECIES_COLLECTION).document(item.species_id).get()
        if not species_doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        # Check if already in favorites
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_SUBCOLLECTION)
            .where("species_id", "==", item.species_id)
            .limit(1)
            .stream()
        )
        if len(list(existing)) > 0:
            raise HTTPException(status_code=400, detail="Species already in favorites")
        
        # Create favorite item
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        item_data = item.model_dump()
        item_data["added_at"] = now
        
        (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_SUBCOLLECTION)
            .document(item_id)
            .set(item_data)
        )
        
        # Return with species details
        item_data["id"] = item_id
        item_data["user_id"] = user_id
        species_details = await get_species_details(item.species_id)
        item_data.update(species_details)
        
        return item_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/me/favorites/{item_id}")
async def remove_from_favorites(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a species from user's favorites"""
    try:
        user_id = current_user["uid"]
        
        doc_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_SUBCOLLECTION)
            .document(item_id)
        )
        
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Favorite item not found")
        
        doc_ref.delete()
        
        return {"message": "Item removed from favorites"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/me/favorites/{species_id}/check")
async def check_if_favorite(
    species_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if a species is in user's favorites"""
    try:
        user_id = current_user["uid"]
        
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_SUBCOLLECTION)
            .where("species_id", "==", species_id)
            .limit(1)
            .stream()
        )
        
        items = list(existing)
        is_favorite = len(items) > 0
        favorite_id = items[0].id if is_favorite else None
        
        return {"is_favorite": is_favorite, "favorite_id": favorite_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/me/collection/{species_id}/check")
async def check_if_in_collection(
    species_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if a species is in user's collection"""
    try:
        user_id = current_user["uid"]
        
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COLLECTION_SUBCOLLECTION)
            .where("species_id", "==", species_id)
            .limit(1)
            .stream()
        )
        
        items = list(existing)
        in_collection = len(items) > 0
        collection_id = items[0].id if in_collection else None
        
        return {"in_collection": in_collection, "collection_id": collection_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# NEWS FAVORITES ENDPOINTS

@router.get("/users/me/favorites/news", response_model=FavoriteNewsListResponse)
async def get_my_favorite_news(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's favorite news"""
    try:
        user_id = current_user["uid"]
        favorites_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_NEWS_SUBCOLLECTION)
        )
        
        # Try with order_by, fallback to unordered if index doesn't exist
        try:
            docs = favorites_ref.order_by("added_at", direction=firestore.Query.DESCENDING).stream()
        except Exception:
            # Fallback: get all without ordering
            docs = favorites_ref.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["user_id"] = user_id
            
            # Enrich with news details
            news_details = await get_news_details(data.get("news_id", ""))
            data.update(news_details)
            
            items.append(data)
        
        # Sort in Python if needed (fallback)
        if items:
            items.sort(key=lambda x: x.get("added_at", datetime.min), reverse=True)
        
        return FavoriteNewsListResponse(items=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/me/favorites/news", response_model=FavoriteNewsSchema)
async def add_news_to_favorites(
    item: FavoriteNewsCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a news item to user's favorites"""
    try:
        user_id = current_user["uid"]
        
        # Verify news exists
        news_doc = db.collection(NEWS_COLLECTION).document(item.news_id).get()
        if not news_doc.exists:
            raise HTTPException(status_code=404, detail="News item not found")
        
        # Check if already in favorites
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_NEWS_SUBCOLLECTION)
            .where("news_id", "==", item.news_id)
            .limit(1)
            .stream()
        )
        if len(list(existing)) > 0:
            raise HTTPException(status_code=400, detail="News already in favorites")
        
        # Create favorite news item
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        item_data = item.model_dump()
        item_data["added_at"] = now
        
        (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_NEWS_SUBCOLLECTION)
            .document(item_id)
            .set(item_data)
        )
        
        # Return with news details
        item_data["id"] = item_id
        item_data["user_id"] = user_id
        news_details = await get_news_details(item.news_id)
        item_data.update(news_details)
        
        return item_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/me/favorites/news/{item_id}")
async def remove_news_from_favorites(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a news item from user's favorites"""
    try:
        user_id = current_user["uid"]
        
        doc_ref = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_NEWS_SUBCOLLECTION)
            .document(item_id)
        )
        
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Favorite news item not found")
        
        doc_ref.delete()
        
        return {"message": "News item removed from favorites"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/me/favorites/news/{news_id}/check", response_model=CheckFavoriteNewsResponse)
async def check_if_news_favorite(
    news_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Check if a news item is in user's favorites"""
    try:
        user_id = current_user["uid"]
        
        existing = (
            db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(FAVORITES_NEWS_SUBCOLLECTION)
            .where("news_id", "==", news_id)
            .limit(1)
            .stream()
        )
        
        items = list(existing)
        is_favorite = len(items) > 0
        favorite_id = items[0].id if is_favorite else None
        
        return CheckFavoriteNewsResponse(is_favorite=is_favorite, favorite_id=favorite_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
