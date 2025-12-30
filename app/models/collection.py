from sqlalchemy import Column, TIMESTAMP, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Collection(Base):
    __tablename__ = "collections"

    collection_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    collection_name = Column(String(100), nullable=False,)
    owner_id = Column(UUID(as_uuid=True), nullable=False,)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    
    __table_args__ = (
        Index('idx_collections_owner', 'owner_id'),
    )