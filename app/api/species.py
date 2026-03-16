"""Species Management API Routes"""
from typing import Annotated, Optional
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, Query
from google.cloud.firestore import Client
from firebase_admin import firestore

from app.models.species import (
    SpeciesSchema,
    SpeciesCreateSchema,
    SpeciesUpdateSchema,
    SpeciesListResponse,
)

# Public routes
router = APIRouter()

# Admin-only routes
admin_router = APIRouter()

db: Client = firestore.client()

SPECIES_COLLECTION = "species"
SPECIES_NOT_FOUND = "Species not found"

_R500 = {500: {"description": "Internal server error"}}
_R404_500 = {404: {"description": SPECIES_NOT_FOUND}, **_R500}


@router.get("/species", response_model=SpeciesListResponse, responses=_R500)
async def list_species(
    search: Annotated[Optional[str], Query(description="Search by name or scientific name")] = None,
    tags: Annotated[Optional[str], Query(description="Comma-separated tags to filter by")] = None,
    colors: Annotated[Optional[str],
                      Query(description="Comma-separated colors to filter by")] = None,
    habitat: Annotated[Optional[str],
                       Query(description="Comma-separated habitats to filter by")] = None,
    distribution: Annotated[Optional[str],
                            Query(description="Comma-separated regions to filter by")] = None,
    province: Annotated[Optional[str],Query(description=
                              "Province name, filters by distribution_v2.provinces")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
):
    """List all species with optional filters."""
    try:
        all_species = []
        for doc in db.collection(SPECIES_COLLECTION).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            all_species.append(data)

        filtered = all_species

        if search:
            q = search.lower()
            filtered = [
                s for s in filtered
                if q in s.get("name", "").lower() or q in s.get("scientific_name", "").lower()
            ]

        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            filtered = [
                s for s in filtered
                if any(tag in [t.lower() for t in s.get("tags", [])] for tag in tag_list)
            ]

        if colors:
            color_list = [c.strip().lower() for c in colors.split(",")]
            filtered = [
                s for s in filtered
                if any(c in [x.lower() for x in s.get("colors", [])] for c in color_list)
            ]

        if habitat:
            hab_list = [h.strip().lower() for h in habitat.split(",")]
            filtered = [
                s for s in filtered
                if any(h in [x.lower() for x in s.get("habitat", [])] for h in hab_list)
            ]

        if distribution:
            dist_list = [d.strip().lower() for d in distribution.split(",")]
            filtered = [
                s for s in filtered
                if any(
                    any(d in dist.lower() or dist.lower()
                        in d for dist in s.get("distribution", []))
                    for d in dist_list
                )
            ]

        if province:
            prov = province.strip().lower()
            filtered = [
                s for s in filtered
                if any(
                    prov in p.lower() or p.lower() in prov
                    for p in (s.get("distribution_v2") or {}).get("provinces", [])
                )
            ]

        total = len(filtered)
        start = (page - 1) * limit
        paginated = filtered[start: start + limit]

        return SpeciesListResponse(species=paginated, total=total, page=page, limit=limit)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/species/{species_id}", response_model=SpeciesSchema, responses=_R404_500)
async def get_species(species_id: str):
    """Get a single species by ID."""
    try:
        doc = db.collection(SPECIES_COLLECTION).document(species_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)
        return {**doc.to_dict(), "id": doc.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.post("/species", response_model=SpeciesSchema, responses=_R500)
async def create_species(species: SpeciesCreateSchema):
    """Create a new species (Admin only)."""
    try:
        species_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        species_data = species.model_dump()
        species_data["created_at"] = now
        species_data["updated_at"] = None

        if species_data.get("classification"):
            species_data["classification"] = dict(species_data["classification"])

        db.collection(SPECIES_COLLECTION).document(species_id).set(species_data)
        return {**species_data, "id": species_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.put("/species/{species_id}", response_model=SpeciesSchema, responses=_R404_500)
async def update_species(species_id: str, species_update: SpeciesUpdateSchema):
    """Update an existing species (Admin only)."""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)

        update_data = species_update.model_dump(exclude_unset=True)

        if update_data.get("classification"):
            update_data["classification"] = dict(update_data["classification"])

        update_data["updated_at"] = datetime.now(timezone.utc)
        doc_ref.update(update_data)

        existing = doc.to_dict()
        existing.update(update_data)
        existing["id"] = species_id
        return existing

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.delete("/species/{species_id}", responses=_R404_500)
async def delete_species(species_id: str):
    """Delete a species (Admin only)."""
    try:
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail=SPECIES_NOT_FOUND)
        doc_ref.delete()
        return {"message": f"Species {species_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
