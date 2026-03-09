"""
Species Management API Routes
CRUD operations for ant species data
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Annotated, Optional, List
from datetime import datetime, timezone
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
SPECIES_NOT_FOUND = "Species not found"


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]):
    """Dependency to check if user is admin"""
    user_ref = db.collection("users").document(current_user["uid"])
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = user_doc.to_dict()
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get(
    "/species",
    response_model=SpeciesListResponse,
    responses={500: {"description": "Internal server error"}}
)
async def list_species(
    search: Annotated[Optional[str], Query(description="Search by name or scientific name")] = None,
    tags: Annotated[Optional[str], Query(description="Comma-separated tags to filter by")] = None,
    colors: Annotated[Optional[str], Query(description="Comma-separated colors to filter by")] = None,
    habitat: Annotated[Optional[str], Query(description="Comma-separated habitats to filter by")] = None,
    distribution: Annotated[Optional[str], Query(description="Comma-separated regions to filter by")] = None,
    province: Annotated[Optional[str], Query(description="Province name — filters by distribution_v2.provinces")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
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
        
        # Distribution filter — uses substring matching in both directions so that
        # "Bangkok" matches "Bangkok Province" and "Bangkok Province" matches "Bangkok"
        if distribution:
            dist_list = [d.strip().lower() for d in distribution.split(",")]
            filtered_species = [
                s for s in filtered_species
                if any(
                    any(
                        d in dist.lower() or dist.lower() in d
                        for dist in s.get("distribution", [])
                    )
                    for d in dist_list
                )
            ]

        # Province filter — checks distribution_v2.provinces (the correct province-level field)
        # Uses substring matching so "Bangkok" matches "Bangkok Province" and vice versa
        if province:
            prov_query = province.strip().lower()
            filtered_species = [
                s for s in filtered_species
                if any(
                    prov_query in p.lower() or p.lower() in prov_query
                    for p in (s.get("distribution_v2") or {}).get("provinces", [])
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


@router.get(
    "/species/{species_id}",
    response_model=SpeciesSchema,
    responses={
        404: {"description": "Species not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_species(species_id: str):
    """Get a single species by ID"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)
        
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/species",
    response_model=SpeciesSchema,
    responses={500: {"description": "Internal server error"}}
)
async def create_species(
    species: SpeciesCreateSchema,
    current_user: Annotated[dict, Depends(require_admin)],
):
    """Create a new species (Admin only)"""
    try:
        species_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
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


@router.put(
    "/species/{species_id}",
    response_model=SpeciesSchema,
    responses={
        404: {"description": "Species not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_species(
    species_id: str,
    species_update: SpeciesUpdateSchema,
    current_user: Annotated[dict, Depends(require_admin)],
):
    """Update an existing species (Admin only)"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)
        
        # Get existing data and update with new values
        existing_data = doc.to_dict()
        update_data = species_update.model_dump(exclude_unset=True)
        
        # Convert classification to dict for Firestore
        if "classification" in update_data and update_data["classification"]:
            update_data["classification"] = dict(update_data["classification"])
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        doc_ref.update(update_data)
        
        # Return updated data
        existing_data.update(update_data)
        existing_data["id"] = species_id
        return existing_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/species/{species_id}",
    responses={
        404: {"description": "Species not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_species(
    species_id: str,
    current_user: Annotated[dict, Depends(require_admin)],
):
    """Delete a species (Admin only)"""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)
        
        doc_ref.delete()
        
        return {"message": f"Species {species_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
