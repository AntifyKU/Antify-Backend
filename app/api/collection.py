"""
Collection and Favorites API Routes
User's personal ant collection and favorites management
"""
from fastapi import APIRouter, HTTPException, Depends
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
)
from app.dependencies.auth import get_current_user

router = APIRouter()
db = firestore.client()

USERS_COLLECTION = "users"
COLLECTION_SUBCOLLECTION = "collection"
FAVORITES_SUBCOLLECTION = "favorites"
SPECIES_COLLECTION = "species"


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


# ============== COLLECTION ENDPOINTS ==============

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


# ============== FAVORITES ENDPOINTS ==============

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
