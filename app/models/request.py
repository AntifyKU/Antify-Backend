from sqlalchemy import Column, TIMESTAMP, Index, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class Request(Base):
    __tablename__ = "requests"
    request_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    request_type = Column(
        String(50),
        nullable=False,
    )
    request_detail = Column(
        JSONB,
        nullable=False,
    )
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
    )
    submitted_by = Column(
        UUID(as_uuid=True),
        nullable=False,
    )
    approved_by = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    rejected_by = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    rejected_reason = Column(
        String(50),
        nullable=True,
    )
    rejection_notes = Column(
        String(100),
        nullable=True,
    )
    species_id = Column(
        String(100),
        nullable=True,
    )
    created_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    
    __table_args__ = (
        Index('idx_requests_status', 'status'),
        Index('idx_requests_submitted_by', 'submitted_by'),
        Index('idx_requests_updated_at', 'updated_at'),
    )