"""Species Management API Routes"""
from typing import Annotated, Optional
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
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
# pylint: disable=duplicate-code


class SpeciesQueryParams(BaseModel):
    """Query params for species listing filters and pagination."""

    search: Optional[str] = Field(default=None, description="Search by name or scientific name")
    tags: Optional[str] = Field(default=None, description="Comma-separated tags to filter by")
    colors: Optional[str] = Field(default=None, description="Comma-separated colors to filter by")
    habitat: Optional[str] = Field(
        default=None,
        description="Comma-separated habitats to filter by",
    )
    distribution: Optional[str] = Field(
        default=None, description="Comma-separated regions to filter by"
    )
    province: Optional[str] = Field(
        default=None, description="Province name, filters by distribution_v2.provinces"
    )
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=500, ge=1, le=1000)


def _split_csv(value: Optional[str]) -> list[str]:
    """Split CSV query values into normalized lowercase tokens."""
    if not value:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _filter_by_contains_list(
    items: list[dict],
    field_name: str,
    candidates: list[str],
) -> list[dict]:
    """Keep items where any candidate is in the given list field."""
    if not candidates:
        return items
    return [
        item
        for item in items
        if any(
            candidate in [v.lower() for v in item.get(field_name, [])]
            for candidate in candidates
        )
    ]


def _filter_by_distribution(items: list[dict], distribution: Optional[str]) -> list[dict]:
    """Filter by partial match against distribution strings."""
    dist_list = _split_csv(distribution)
    if not dist_list:
        return items
    return [
        item
        for item in items
        if any(
            any(d in dist.lower() or dist.lower() in d for dist in item.get("distribution", []))
            for d in dist_list
        )
    ]


def _filter_by_province(items: list[dict], province: Optional[str]) -> list[dict]:
    """Filter by partial match against distribution_v2.provinces."""
    if not province:
        return items
    prov = province.strip().lower()
    return [
        item
        for item in items
        if any(
            prov in p.lower() or p.lower() in prov
            for p in (item.get("distribution_v2") or {}).get("provinces", [])
        )
    ]


def _apply_species_filters(all_species: list[dict], params: SpeciesQueryParams) -> list[dict]:
    """Apply all optional species filters."""
    filtered = all_species

    if params.search:
        query_text = params.search.lower()
        filtered = [
            item
            for item in filtered
            if query_text in item.get("name", "").lower()
            or query_text in item.get("scientific_name", "").lower()
        ]

    filtered = _filter_by_contains_list(filtered, "tags", _split_csv(params.tags))
    filtered = _filter_by_contains_list(filtered, "colors", _split_csv(params.colors))
    filtered = _filter_by_contains_list(filtered, "habitat", _split_csv(params.habitat))
    filtered = _filter_by_distribution(filtered, params.distribution)
    return _filter_by_province(filtered, params.province)


@router.get("/species", response_model=SpeciesListResponse, responses=_R500)
async def list_species(
    params: Annotated[SpeciesQueryParams, Depends()],
):
    """List all species with optional filters."""
    try:
        all_species = []
        for doc in db.collection(SPECIES_COLLECTION).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            all_species.append(data)

        filtered = _apply_species_filters(all_species, params)

        total = len(filtered)
        start = (params.page - 1) * params.limit
        paginated = filtered[start: start + params.limit]

        return SpeciesListResponse(
            species=paginated,
            total=total,
            page=params.page,
            limit=params.limit,
        )

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
