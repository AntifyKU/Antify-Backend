from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime


class SignUpSchema(BaseModel):
    """User sign-up schema"""
    username: str
    email: EmailStr
    password: str

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "password": "strongpassword123"
            }
        }


class UserSchema(BaseModel):
    """User schema"""
    user_id: str
    username: str
    email: EmailStr
    role: str = "user"
    profile_picture: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    preferences: Dict[str, object] = {
        "language": "english",
        "theme": "light",
        "notifications_enabled": True
    }

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "uuid-string",
                "username": "johndoe",
                "email": "johndoe@example.com",
                "role": "user",
                "profile_picture": None,
                "is_active": True,
                "created_at": "2026-01-07T10:00:00",
                "preferences": {
                    "language": "english",
                    "theme": "light",
                    "notifications_enabled": True
                }
            }
        }
