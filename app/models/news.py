from sqlalchemy import Column, String, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class News(Base):
    __tablename__ = "news"

    news_id = Column(
        UUID(as_uuid=True),
        primary_key=True
    )
    news_title = Column(String(255), nullable=False)
    news_url = Column(String(500), nullable=False)
    news_source = Column(String(100), nullable=False)
    published_date = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (
        Index('idx_news_published_date', 'published_date'),
    )
