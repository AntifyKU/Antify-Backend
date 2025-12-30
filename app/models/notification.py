from sqlalchemy import Column, TIMESTAMP, String, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
    )
    notification_type = Column(
        String(50),
        nullable=False,
    )
    title = Column(
        String(255),
        nullable=False,
    )
    description = Column(
        String,
        nullable=False,
    )
    reference_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    is_read = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )
    created_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    
    __table_args__ = (
        Index('idx_notifications_user', 'user_id', 'is_read'),
        Index('idx_notifications_created_at', created_at.desc()),
    )