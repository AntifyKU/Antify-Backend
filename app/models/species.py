"""
Species Pydantic Models
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ClassificationSchema(BaseModel):
    """Ant classification taxonomy"""
    family: str = "Formicidae"
    subfamily: str
    genus: str


class SpeciesBase(BaseModel):
    """Base species schema with common fields"""
    model_config = ConfigDict(extra="allow")
    name: str = Field(..., description="Common name of the ant species")
    scientific_name: str = Field(..., description="Scientific name (Latin)")
    classification: ClassificationSchema
    tags: List[str] = Field(default_factory=list, description="Descriptive tags")
    about: str = Field(..., description="General description")
    characteristics: str = Field(..., description="Physical characteristics")
    colors: List[str] = Field(default_factory=list)
    habitat: List[str] = Field(default_factory=list)
    distribution: List[str] = Field(default_factory=list, description="Geographic regions")
    behavior: str = Field(..., description="Behavioral traits")
    ecological_role: str = Field(..., description="Role in ecosystem")
    image: str = Field(..., description="Image URL")


class SpeciesCreateSchema(SpeciesBase):
    """Schema for creating a new species"""

    class Config:
        """Example Format"""
        json_schema_extra = {
            "example": {
                "name": "Weaver Ant",
                "scientific_name": "Oecophylla smaragdina",
                "classification": {
                    "family": "Formicidae",
                    "subfamily": "Formicinae",
                    "genus": "Oecophylla"
                },
                "tags": ["Tree-dwelling", "Beneficial", "Edible"],
                "about": "Weaver ants are remarkable architects...",
                "characteristics": "Workers range from 5-10mm...",
                "colors": ["Orange", "Red-brown"],
                "habitat": ["Tropical Trees", "Orchards"],
                "distribution": ["Central", "East", "South"],
                "behavior": "Highly social with complex division of labor...",
                "ecological_role": "Important biological pest control agents...",
                "image": "https://example.com/weaver-ant.jpg"
            }
        }


class SpeciesUpdateSchema(BaseModel):
    """Schema for updating species (all fields optional)"""
    name: Optional[str] = None
    scientific_name: Optional[str] = None
    classification: Optional[ClassificationSchema] = None
    tags: Optional[List[str]] = None
    about: Optional[str] = None
    characteristics: Optional[str] = None
    colors: Optional[List[str]] = None
    habitat: Optional[List[str]] = None
    distribution: Optional[List[str]] = None
    behavior: Optional[str] = None
    ecological_role: Optional[str] = None
    image: Optional[str] = None


class SpeciesSchema(SpeciesBase):
    """Full species schema with ID and timestamps"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Example Format"""
        from_attributes = True


class SpeciesListResponse(BaseModel):
    """Response schema for listing species"""
    species: List[SpeciesSchema]
    total: int
    page: int = 1
    limit: int = 500
