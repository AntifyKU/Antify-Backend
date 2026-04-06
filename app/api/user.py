"""User authentication & management endpoints"""
from datetime import datetime, timezone
from typing import Optional, Annotated
import uuid
import io
import traceback

from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

import cloudinary
import cloudinary.uploader
import requests

from firebase_admin import auth, firestore

from app.models.user import (
    SignUpSchema,
    LoginSchema,
    UserSchema,
    ChangePasswordSchema,
    UpdateProfileSchema,
    ChangeEmailSchema,
)
from app.dependencies.auth import get_current_user
from app.firebase import firebase

# pylint: disable=duplicate-code

# Public routes (no admin required)
router = APIRouter()

# Admin-only routes
# so these handler functions have no auth parameter in their signatures.
admin_router = APIRouter()

db = firestore.client()

CLOUDINARY_DOMAIN = "cloudinary.com"
USER_NOT_FOUND = "User not found"
INTERNAL_SERVER_ERROR = "Internal server error"


def _extract_cloudinary_public_id(url: str) -> str:
    """Extract the Cloudinary public_id from a secure URL."""
    after_upload = url.split("/upload/")[-1]
    parts = after_upload.split("/")
    if parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    return "/".join(parts).rsplit(".", 1)[0]


@router.post(
    "/auth/signup",
    responses={
        400: {"description": "Username or email already exists"},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def create_new_account(user: SignUpSchema):
    """Create a new user account."""
    try:
        users_ref = db.collection("users")
        if users_ref.where("username", "==", user.username).limit(1).get():
            raise HTTPException(status_code=400, detail="Username already exists")

        firebase_user = auth.create_user(
            display_name=user.username, email=user.email, password=user.password
        )

        user_data = UserSchema(
            user_id=firebase_user.uid,
            username=user.username,
            email=user.email,
            created_at=datetime.now(timezone.utc),
        )
        try:
            db.collection("users").document(firebase_user.uid).set(user_data.model_dump())
        except Exception as e:
            auth.delete_user(firebase_user.uid)
            raise e

        return JSONResponse(status_code=201, content={"message": "User created successfully"})

    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already exists") from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/auth/login",
    responses={
        400: {"description": "Invalid username or password"},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def login_user(user: LoginSchema):
    """Login user with username/email and password."""
    email = user.email.strip()

    try:
        if "@" not in email:
            query = db.collection("users").where("username", "==", email).limit(1).get()
            if not query:
                raise HTTPException(status_code=400, detail="Invalid username or email")
            email = query[0].to_dict()["email"]

        try:
            user_cred = firebase.auth().sign_in_with_email_and_password(email, user.password)
        except requests.HTTPError as exc:
            raise HTTPException(status_code=400, detail="Invalid username or password") from exc

        firebase_user = auth.get_user_by_email(email)
        db.collection("users").document(firebase_user.uid).update(
            {"lasted_login": datetime.now(timezone.utc)}
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Login successful",
                "user_id": firebase_user.uid,
                "id_token": user_cred["idToken"],
                "refresh_token": user_cred["refreshToken"],
                "expires_in": user_cred.get("expiresIn", "3600"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/auth/logout", responses={500: {"description": INTERNAL_SERVER_ERROR}})
async def logout_user(current_user: Annotated[dict, Depends(get_current_user)]):
    """Logout user, revokes all refresh tokens."""
    try:
        auth.revoke_refresh_tokens(current_user["uid"])
        return JSONResponse(status_code=200, content={"message": "User logged out successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/users/me",
    response_model=UserSchema,
    responses={
        404: {"description": USER_NOT_FOUND},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def get_account_info(current_user: Annotated[dict, Depends(get_current_user)]):
    """Get current user account info."""
    try:
        user_doc = db.collection("users").document(current_user["uid"]).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
        return UserSchema(**user_doc.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/users/me",
    responses={
        404: {"description": USER_NOT_FOUND},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def delete_my_account(current_user: Annotated[dict, Depends(get_current_user)]):
    """Delete current user account and all associated data."""
    try:
        uid = current_user["uid"]

        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            pic = user_doc.to_dict().get("profile_picture")
            if pic and CLOUDINARY_DOMAIN in pic:
                try:
                    cloudinary.uploader.destroy(_extract_cloudinary_public_id(pic))
                except cloudinary.exceptions.Error as e:
                    print(f"Warning: Could not delete Cloudinary profile picture: {e}")

        db.collection("users").document(uid).delete()
        auth.delete_user(uid)

        return JSONResponse(status_code=200, content={"message": "Account deleted successfully"})

    except auth.UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put(
    "/users/me/profile",
    responses={
        400: {"description": "Username already exists"},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def update_profile(
    profile: UpdateProfileSchema,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update user profile fields."""
    try:
        uid = current_user["uid"]
        update_data = profile.model_dump(exclude_unset=True, exclude_none=True)

        if not update_data:
            return JSONResponse(status_code=200, content={"message": "No changes to update"})

        if "username" in update_data:
            query = (
                db.collection("users")
                .where("username", "==", update_data["username"])
                .limit(1)
                .get()
            )
            if query and query[0].id != uid:
                raise HTTPException(status_code=400, detail="Username already exists")

        update_data["lasted_update"] = datetime.now(timezone.utc)
        db.collection("users").document(uid).update(update_data)

        return JSONResponse(status_code=200,
                            content={"message": "User profile updated successfully"})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating profile: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e


@router.put(
    "/users/me/email",
    responses={
        400: {"description": "Email already in use"},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def change_email(
    email_change: ChangeEmailSchema,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Change user email."""
    try:
        uid = current_user["uid"]
        auth.update_user(uid, email=email_change.new_email)
        db.collection("users").document(uid).update(
            {"email": email_change.new_email, "lasted_update": datetime.now(timezone.utc)}
        )
        return JSONResponse(status_code=200, content={"message": "Email updated successfully"})

    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already in use") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/users/me/password", responses={500: {"description": INTERNAL_SERVER_ERROR}})
async def change_password(
    password_change: ChangePasswordSchema,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Change user password."""
    try:
        auth.update_user(current_user["uid"], password=password_change.new_password)
        return JSONResponse(status_code=200, content={"message": "Password updated successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/users/me/profile-picture",
    responses={
        400: {"description": "Invalid file type or file too large"},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def upload_profile_picture(
    current_user: Annotated[dict, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
):
    """Upload a new profile picture (stored on Cloudinary)."""
    try:
        uid = current_user["uid"]

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Allowed: JPEG, PNG, GIF, WEBP",
            )

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 5 MB")

        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            old_pic = user_doc.to_dict().get("profile_picture")
            if old_pic and CLOUDINARY_DOMAIN in old_pic:
                try:
                    cloudinary.uploader.destroy(_extract_cloudinary_public_id(old_pic))
                except (cloudinary.exceptions.Error, ValueError, IndexError, KeyError) as e:
                    print(f"Warning: Could not delete old Cloudinary picture: {e}")

        upload_result = cloudinary.uploader.upload(
            io.BytesIO(content),
            folder=f"profile_pictures/{uid}",
            public_id=str(uuid.uuid4()),
            resource_type="image",
            overwrite=True,
        )
        public_url = upload_result["secure_url"]

        db.collection("users").document(uid).update(
            {"profile_picture": public_url, "lasted_update": datetime.now(timezone.utc)}
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Profile picture uploaded successfully",
                "profile_picture_url": public_url,
            },
        )
    except (cloudinary.exceptions.Error, KeyError, ValueError) as e:
        print(f"Error uploading profile picture: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/users/me/profile-picture",
    responses={
        404: {"description": USER_NOT_FOUND},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def delete_profile_picture(current_user: Annotated[dict, Depends(get_current_user)]):
    """Delete user's current profile picture from Cloudinary."""
    try:
        uid = current_user["uid"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

        pic_url = user_doc.to_dict().get("profile_picture")
        if pic_url and CLOUDINARY_DOMAIN in pic_url:
            try:
                cloudinary.uploader.destroy(_extract_cloudinary_public_id(pic_url))
            except cloudinary.exceptions.Error as e:
                print(f"Warning: Could not delete Cloudinary picture: {e}")

        db.collection("users").document(uid).update(
            {"profile_picture": None, "lasted_update": datetime.now(timezone.utc)}
        )

        return JSONResponse(status_code=200,
                            content={"message": "Profile picture deleted successfully"})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class PushTokenSchema(BaseModel):
    """Schema for push token data."""
    push_token: str
    platform: str
    device_id: Optional[str] = None


@router.post("/users/me/push-token", responses={500: {"description": INTERNAL_SERVER_ERROR}})
async def register_push_token(
    token_data: PushTokenSchema,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Register a push notification token for the current user."""
    try:
        db.collection("users").document(current_user["uid"]).update(
            {
                "push_token": token_data.push_token,
                "push_platform": token_data.platform,
                "push_device_id": token_data.device_id,
                "push_token_updated_at": datetime.now(timezone.utc),
            }
        )
        return JSONResponse(status_code=200,
                            content={"message": "Push token registered successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/push-token", responses={500: {"description": INTERNAL_SERVER_ERROR}})
async def unregister_push_token(current_user: Annotated[dict, Depends(get_current_user)]):
    """Unregister push notification token for the current user."""
    try:
        db.collection("users").document(current_user["uid"]).update(
            {
                "push_token": None,
                "push_platform": None,
                "push_device_id": None,
                "push_token_updated_at": datetime.now(timezone.utc),
            }
        )
        return JSONResponse(status_code=200,
                            content={"message": "Push token unregistered successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/users/me/push-token",
    responses={
        404: {"description": USER_NOT_FOUND},
        500: {"description": INTERNAL_SERVER_ERROR},
    },
)
async def get_push_token(current_user: Annotated[dict, Depends(get_current_user)]):
    """Get the current user's push token info."""
    try:
        uid = current_user["uid"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=USER_NOT_FOUND)

        data = user_doc.to_dict()
        updated_at = data.get("push_token_updated_at")
        return JSONResponse(
            status_code=200,
            content={
                "push_token": data.get("push_token"),
                "platform": data.get("push_platform"),
                "device_id": data.get("push_device_id"),
                "updated_at": updated_at.isoformat() if updated_at else None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@admin_router.get("/users", responses={500: {"description": INTERNAL_SERVER_ERROR}})
async def list_all_users():
    """List all users (Admin only)."""
    try:
        users = []
        for doc in db.collection("users").stream():
            try:
                users.append(UserSchema(**doc.to_dict()).model_dump(mode="json"))
            except (ValueError, KeyError) as e:
                print(f"Error processing user {doc.id}: {e}")
        return JSONResponse(status_code=200, content={"users": users})

    except Exception as e:
        print(f"Error listing users: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e
