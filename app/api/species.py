"""
Species Management API Routes
CRUD operations for ant species data
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime
import uuid

from firebase_admin import firestore
from app.models.species import (
    SpeciesSchema,
    SpeciesCreateSchema,
    SpeciesUpdateSchema,
    SpeciesListResponse,
)
from app.dependencies.auth import get_current_user

router = APIRouter()
db = firestore.client()
SPECIES_COLLECTION = "species"


def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency to check if user is admin"""
    user_ref = db.collection("users").document(current_user["uid"])
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = user_doc.to_dict()
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/species", response_model=SpeciesListResponse)
async def list_species(
    search: Optional[str] = Query(None, description="Search by name or scientific name"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    colors: Optional[str] = Query(None, description="Comma-separated colors to filter by"),
    habitat: Optional[str] = Query(None, description="Comma-separated habitats to filter by"),
    distribution: Optional[str] = Query(None, description="Comma-separated regions to filter by"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """
    List all species with optional filters.
    Filters are applied client-side due to Firestore limitations.
    """
    try:
        # Get all species from Firestore
        species_ref = db.collection(SPECIES_COLLECTION)
        docs = species_ref.stream()
        
        all_species = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            all_species.append(data)
        
        # Apply filters
        filtered_species = all_species
        
        # Search filter (name or scientific_name)
        if search:
            search_lower = search.lower()
            filtered_species = [
                s for s in filtered_species
                if search_lower in s.get("name", "").lower()
                or search_lower in s.get("scientific_name", "").lower()
            ]
        
        # Tags filter
        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            filtered_species = [
                s for s in filtered_species
                if any(
                    tag.lower() in [t.lower() for t in s.get("tags", [])]
                    for tag in tag_list
                )
            ]
        
        # Colors filter
        if colors:
            color_list = [c.strip().lower() for c in colors.split(",")]
            filtered_species = [
                s for s in filtered_species
                if any(
                    color.lower() in [c.lower() for c in s.get("colors", [])]
                    for color in color_list
                )
            ]
        
        # Habitat filter
        if habitat:
            habitat_list = [h.strip().lower() for h in habitat.split(",")]
            filtered_species = [
                s for s in filtered_species
                if any(
                    h.lower() in [hab.lower() for hab in s.get("habitat", [])]
                    for h in habitat_list
                )
            ]
        
        # Distribution filter
        if distribution:
            dist_list = [d.strip().lower() for d in distribution.split(",")]
            filtered_species = [
                s for s in filtered_species
                if any(
                    d.lower() in [dist.lower() for dist in s.get("distribution", [])]
                    for d in dist_list
                )
            ]
        
        # Pagination
        total = len(filtered_species)
        start = (page - 1) * limit
        end = start + limit
        paginated_species = filtered_species[start:end]
        
        return SpeciesListResponse(
            species=paginated_species,
            total=total,
            page=page,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/species/{species_id}", response_model=SpeciesSchema)
async def get_species(species_id: str):
    """Get a single species by ID"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/species", response_model=SpeciesSchema)
async def create_species(
    species: SpeciesCreateSchema,
    current_user: dict = Depends(require_admin),
):
    """Create a new species (Admin only)"""
    try:
        species_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        species_data = species.model_dump()
        species_data["created_at"] = now
        species_data["updated_at"] = None
        
        # Convert classification to dict for Firestore
        if "classification" in species_data and species_data["classification"]:
            species_data["classification"] = dict(species_data["classification"])
        
        db.collection(SPECIES_COLLECTION).document(species_id).set(species_data)
        
        species_data["id"] = species_id
        return species_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/species/{species_id}", response_model=SpeciesSchema)
async def update_species(
    species_id: str,
    species_update: SpeciesUpdateSchema,
    current_user: dict = Depends(require_admin),
):
    """Update an existing species (Admin only)"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        # Get existing data and update with new values
        existing_data = doc.to_dict()
        update_data = species_update.model_dump(exclude_unset=True)
        
        # Convert classification to dict for Firestore
        if "classification" in update_data and update_data["classification"]:
            update_data["classification"] = dict(update_data["classification"])
        
        update_data["updated_at"] = datetime.utcnow()
        
        doc_ref.update(update_data)
        
        # Return updated data
        existing_data.update(update_data)
        existing_data["id"] = species_id
        return existing_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/species/{species_id}")
async def delete_species(
    species_id: str,
    current_user: dict = Depends(require_admin),
):
    """Delete a species (Admin only)"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Species not found")
        
        doc_ref.delete()
        
        return {"message": f"Species {species_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
