from sqlalchemy import Column, String, Boolean, TIMESTAMP, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(
        UUID(as_uuid=True), 
        primary_key=True
    )
    username = Column(String(50), unique=True, nullable=False)
    role = Column(String(20), nullable=False, default='user')
    profile_image_url = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_login = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin')",
            name='check_role'
        ),
        Index('idx_profiles_username', 'username'),
    )