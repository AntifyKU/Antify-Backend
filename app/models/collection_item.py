from sqlalchemy import Column, TIMESTAMP, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class CollectionItem(Base):
    __tablename__ = "collection_items"

    item_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    collection_id = Column(
        UUID(as_uuid=True),
        nullable=False,
    )
    species_id = Column(
        String(100),
        nullable=False,
    )
    added_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    
    __table_args__ = (
        Index('idx_collection_items_collection', 'collection_id'),
        Index('idx_collection_items_species', 'species_id'),
        Index('uq_collection_species', 'collection_id', 'species_id', unique=True),
    )