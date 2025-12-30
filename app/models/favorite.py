from sqlalchemy import Column, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class Favorite(Base):
    __tablename__ = "favorites"

    favorite_id = Column(
        UUID(as_uuid=True),
        primary_key=True
    )
    user_id = Column(UUID(as_uuid=True), nullable=False)
    news_id = Column(UUID(as_uuid=True), nullable=False)
    added_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_favorite_user_news', 'user_id', 'news_id', unique=True),
    )