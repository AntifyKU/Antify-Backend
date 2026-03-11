from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi import APIRouter, Depends, UploadFile, File
from app.models.user import SignUpSchema, LoginSchema, UserSchema, ChangePasswordSchema, UpdateProfileSchema, ChangeEmailSchema
from app.dependencies.auth import get_current_user, verify_token

from datetime import datetime, timezone
from typing import Optional
import uuid
import io
import traceback

import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import auth, firestore
import app.config
from app.firebase import firebase
import requests

from pydantic import BaseModel

router = APIRouter()
db = firestore.client()


def _extract_cloudinary_public_id(url: str) -> str:
    """
    Extract the Cloudinary public_id from a secure URL.

    Example URL:
      https://res.cloudinary.com/<cloud>/image/upload/v1234567890/profile_pictures/uid/abc.jpg
    Returns:
      profile_pictures/uid/abc
    """
    # Everything after "/upload/"
    after_upload = url.split("/upload/")[-1]
    # Drop optional version segment (v<digits>/)
    parts = after_upload.split("/")
    if parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    # Drop file extension
    path_no_ext = "/".join(parts).rsplit(".", 1)[0]
    return path_no_ext


@router.post("/auth/signup")
async def create_new_account(user: SignUpSchema):
    """Create a new user account"""
    username = user.username
    email = user.email
    password = user.password

    try:
        # Check if username already exists in Firestore
        users_ref = db.collection("users")
        query = users_ref.where("username", "==", username).limit(1).get()
        if query:
            raise HTTPException(status_code=400, detail="Username already exists")

        # Create user in Firebase Authentication
        firebase_user = auth.create_user(display_name=username, email=email, password=password)

        # Add user to Firestore
        user_data = UserSchema(
            user_id=firebase_user.uid,
            username=username,
            email=email,
            created_at=datetime.now(timezone.utc),
        )
        try:
            db.collection("users").document(firebase_user.uid).set(user_data.model_dump())
        except Exception as e:
            # Rollback Firebase Auth user if Firestore write fails
            auth.delete_user(firebase_user.uid)
            raise e

        return JSONResponse(status_code=201, content={"message": "User created successfully"})

    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already exists") from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/auth/login")
async def login_user(user: LoginSchema):
    """Login user with username/email and password"""
    username_or_email = user.username_or_email.strip()
    password = user.password

    try:
        # Resolve username → email
        if "@" not in username_or_email:
            query = (
                db.collection("users")
                .where("username", "==", username_or_email)
                .limit(1)
                .get()
            )
            if not query:
                raise HTTPException(status_code=400, detail="Invalid username or email")
            email = query[0].to_dict()["email"]
        else:
            email = username_or_email

        # Sign in via Firebase REST API
        try:
            user_cred = firebase.auth().sign_in_with_email_and_password(email, password)
        except requests.HTTPError as exc:
            raise HTTPException(status_code=400, detail="Invalid username or password") from exc

        # Get Firebase user info & update last-login timestamp
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
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/auth/logout")
async def logout_user(current_user=Depends(get_current_user)):
    """Logout user — revokes all refresh tokens"""
    try:
        uid = current_user["uid"]
        auth.revoke_refresh_tokens(uid)
        return JSONResponse(status_code=200, content={"message": "User logged out successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/users/me", response_model=UserSchema)
async def get_account_info(current_user=Depends(get_current_user)):
    """Get current user account info"""
    try:
        uid = current_user["uid"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        return UserSchema(**user_doc.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me")
async def delete_my_account(current_user=Depends(get_current_user)):
    """Delete current user account and all associated data"""
    try:
        uid = current_user["uid"]

        # Delete profile picture from Cloudinary (if any)
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            data = user_doc.to_dict()
            pic = data.get("profile_picture")
            if pic and "cloudinary.com" in pic:
                try:
                    public_id = _extract_cloudinary_public_id(pic)
                    cloudinary.uploader.destroy(public_id)
                except Exception as e:
                    print(f"Warning: Could not delete Cloudinary profile picture: {e}")

        # Delete Firestore document
        db.collection("users").document(uid).delete()

        # Delete from Firebase Auth
        auth.delete_user(uid)

        return JSONResponse(status_code=200, content={"message": "Account deleted successfully"})

    except auth.UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/users/me/profile")
async def update_profile(
    profile: UpdateProfileSchema,
    current_user=Depends(get_current_user),
):
    """Update user profile fields"""
    try:
        uid = current_user["uid"]
        update_data = profile.model_dump(exclude_unset=True, exclude_none=True)

        if not update_data:
            return JSONResponse(status_code=200, content={"message": "No changes to update"})

        # Check username uniqueness if being changed
        if "username" in update_data:
            username = update_data["username"]
            query = (
                db.collection("users")
                .where("username", "==", username)
                .limit(1)
                .get()
            )
            if query and query[0].id != uid:
                raise HTTPException(status_code=400, detail="Username already exists")

        update_data["lasted_update"] = datetime.now(timezone.utc)
        db.collection("users").document(uid).update(update_data)

        return JSONResponse(status_code=200, content={"message": "User profile updated successfully"})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@router.put("/users/me/email")
async def change_email(
    email_change: ChangeEmailSchema,
    current_user=Depends(get_current_user),
):
    """Change user email"""
    try:
        uid = current_user["uid"]
        new_email = email_change.new_email

        auth.update_user(uid, email=new_email)
        db.collection("users").document(uid).update(
            {"email": new_email, "lasted_update": datetime.now(timezone.utc)}
        )

        return JSONResponse(status_code=200, content={"message": "Email updated successfully"})

    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already in use") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/users/me/password")
async def change_password(
    password_change: ChangePasswordSchema,
    current_user=Depends(get_current_user),
):
    """Change user password"""
    try:
        uid = current_user["uid"]
        auth.update_user(uid, password=password_change.new_password)
        return JSONResponse(status_code=200, content={"message": "Password updated successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/users/me/profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Upload a new profile picture (stored on Cloudinary)"""
    try:
        uid = current_user["uid"]

        # Validate MIME type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Allowed: JPEG, PNG, GIF, WEBP",
            )

        content = await file.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 5 MB",
            )

        # Delete previous profile picture from Cloudinary (if any)
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            old_pic = user_doc.to_dict().get("profile_picture")
            if old_pic and "cloudinary.com" in old_pic:
                try:
                    old_public_id = _extract_cloudinary_public_id(old_pic)
                    cloudinary.uploader.destroy(old_public_id)
                except Exception as e:
                    print(f"Warning: Could not delete old Cloudinary picture: {e}")

        # Upload new picture to Cloudinary
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(content),
            folder=f"profile_pictures/{uid}",
            public_id=str(uuid.uuid4()),
            resource_type="image",
            overwrite=True,
            # Optional: auto-crop to a square thumbnail on delivery
            # transformation=[{"width": 400, "height": 400, "crop": "fill", "gravity": "face"}],
        )
        public_url = upload_result["secure_url"]

        # Persist URL to Firestore
        db.collection("users").document(uid).update(
            {
                "profile_picture": public_url,
                "lasted_update": datetime.now(timezone.utc),
            }
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Profile picture uploaded successfully",
                "profile_picture_url": public_url,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/profile-picture")
async def delete_profile_picture(current_user=Depends(get_current_user)):
    """Delete user's current profile picture from Cloudinary"""
    try:
        uid = current_user["uid"]

        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

        current_pic_url = user_doc.to_dict().get("profile_picture")

        if current_pic_url and "cloudinary.com" in current_pic_url:
            try:
                public_id = _extract_cloudinary_public_id(current_pic_url)
                cloudinary.uploader.destroy(public_id)
            except Exception as e:
                print(f"Warning: Could not delete Cloudinary picture: {e}")

        db.collection("users").document(uid).update(
            {
                "profile_picture": None,
                "lasted_update": datetime.now(timezone.utc),
            }
        )

        return JSONResponse(
            status_code=200, content={"message": "Profile picture deleted successfully"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def require_admin(user=Depends(get_current_user)):
    """Dependency — ensures the current user has the 'admin' role"""
    try:
        uid = user["uid"]
        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = doc.to_dict()
        if not user_data or user_data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in require_admin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking admin status: {str(e)}") from e


@router.get("/users")
async def list_all_users(admin_user=Depends(require_admin)):
    """List all users (admin only)"""
    try:
        users = []
        for doc in db.collection("users").stream():
            try:
                user = UserSchema(**doc.to_dict())
                users.append(user.model_dump(mode="json"))
            except Exception as e:
                print(f"Error processing user {doc.id}: {str(e)}")
                continue

        return JSONResponse(status_code=200, content={"users": users})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


class PushTokenSchema(BaseModel):
    push_token: str
    platform: str          # 'ios' or 'android'
    device_id: Optional[str] = None


@router.post("/users/me/push-token")
async def register_push_token(
    token_data: PushTokenSchema,
    current_user=Depends(get_current_user),
):
    """Register a push notification token for the current user"""
    try:
        uid = current_user["uid"]
        db.collection("users").document(uid).update(
            {
                "push_token": token_data.push_token,
                "push_platform": token_data.platform,
                "push_device_id": token_data.device_id,
                "push_token_updated_at": datetime.now(timezone.utc),
            }
        )
        return JSONResponse(status_code=200, content={"message": "Push token registered successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/me/push-token")
async def unregister_push_token(current_user=Depends(get_current_user)):
    """Unregister push notification token for the current user"""
    try:
        uid = current_user["uid"]
        db.collection("users").document(uid).update(
            {
                "push_token": None,
                "push_platform": None,
                "push_device_id": None,
                "push_token_updated_at": datetime.now(timezone.utc),
            }
        )
        return JSONResponse(status_code=200, content={"message": "Push token unregistered successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/users/me/push-token")
async def get_push_token(current_user=Depends(get_current_user)):
    """Get the current user's push token info"""
    try:
        uid = current_user["uid"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")

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
