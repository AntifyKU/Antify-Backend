"""Users Model"""
from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr


class SignUpSchema(BaseModel):
    """User sign-up schema"""
    username: str
    email: EmailStr
    password: str

    class Config:
        """Example Format"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "password": "strongpassword123"
            }
        }

class LoginSchema(BaseModel):
    """User login schema"""
    email: str
    password: str

    class Config:
        """Example Format"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "email": "johndoe",
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
    lasted_login: Optional[datetime] = None
    lasted_update: Optional[datetime] = None
    preferences: Dict[str, object] = {
        "language": "english",
    }

    class Config:
        """Example Format"""
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
                "lasted_login": "2026-01-10T15:30:00",
                "lasted_update": "2026-01-15T12:45:00",
                "preferences": {
                    "language": "english",
                }
            }
        }

class UpdateProfileSchema(BaseModel):
    """User profile update schema"""
    username: Optional[str] = None
    profile_picture: Optional[str] = None
    preferences: Optional[dict] = None

    class Config:
        """Example Format"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "username": "john_doe_updated",
                "profile_picture": "http://example.com/profile.jpg",
                "preferences": {
                    "language": "spanish",
                }
            }
        }

class ChangeEmailSchema(BaseModel):
    """Change email schema"""
    new_email: EmailStr

    class Config:
        """Example Format"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "new_email": "newemail@example.com"
            }
        }

class ChangePasswordSchema(BaseModel):
    """Change password schema"""
    new_password: str

    class Config:
        """Example Format"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "new_password": "newstrongpassword456"
            }
        }
