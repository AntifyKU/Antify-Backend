from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi import APIRouter, Depends
from app.models.user import SignUpSchema, LoginSchema, UserSchema, ChangePasswordSchema, UpdateProfileSchema, ChangeEmailSchema
from app.dependencies.auth import get_current_user, verify_token

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth, firestore
from app.firebase import firebase
import requests
import traceback

router = APIRouter()
db = firestore.client()

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
        # If not, create user in Firebase Authentication
        firebase_user = auth.create_user(display_name=username, email=email, password=password)
        # Add user to Firestore
        user_data = UserSchema(
            user_id=firebase_user.uid,
            username=username,
            email=email,
            created_at=datetime.now(timezone.utc)
        )
        try:
            db.collection("users").document(firebase_user.uid).set(
                user_data.model_dump()
            )
        except Exception as e:
            # Rollback user creation in Firebase Auth if Firestore write fails
            auth.delete_user(firebase_user.uid)
            raise e
        return JSONResponse(status_code=201, content={"message": "User created successfully"})
    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already exists") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/auth/login")
async def login_user(user: LoginSchema):
    """Login user with username/email and password"""
    username_or_email = user.username_or_email.strip()
    password = user.password

    try:
        # Find email if username is provided
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
        # Login with email and password
        try:
            user_cred = firebase.auth().sign_in_with_email_and_password(
                email, password
            )
        except requests.HTTPError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid username or password"
            ) from exc
        # Get firebase user info
        firebase_user = auth.get_user_by_email(email)
        # Update last login time
        db.collection("users").document(firebase_user.uid).update({
            "lasted_login": datetime.now(timezone.utc)
        })
        return JSONResponse(
            status_code=200,
            content={
                "message": "Login successful",
                "user_id": firebase_user.uid,
                "id_token": user_cred["idToken"],
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/users/me", response_model=UserSchema)
async def get_account_info(current_user=Depends(get_current_user)):
    """Get user account info"""
    try:
        # Fetch user document from Firestore
        uid = current_user["uid"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        # Convert Firestore document to UserSchema
        user_data = user_doc.to_dict()
        return UserSchema(**user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.delete("/users/me")
async def delete_my_account(current_user=Depends(get_current_user)):
    """Delete user account by user ID"""
    try:
        # Delete user from Firebase Authentication
        user_id = current_user["uid"]
        auth.delete_user(user_id)
        # Delete user document from Firestore
        db.collection("users").document(user_id).delete()
        return JSONResponse(status_code=200,
                            content={"message": "User account deleted successfully"})
    except auth.UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.put("/users/me/profile")
async def update_profile(profile: UpdateProfileSchema, 
                         current_user=Depends(get_current_user)):
    """Update user profile"""
    try:
        uid = current_user["uid"]
        # Get only the fields that were provided (exclude None values)
        update_data = profile.model_dump(exclude_unset=True, exclude_none=True)

        # If no data to update, return early
        if not update_data:
            return JSONResponse(status_code=200,
                              content={"message": "No changes to update"})

        # If username is being updated, check for uniqueness
        if "username" in update_data:
            username = update_data["username"]
            # Query for existing username
            query = (
                db.collection("users")
                .where("username", "==", username)
                .limit(1)
                .get()
            )
            # Check if username exists and belongs to a different user
            if query:
                existing_user = query[0]
                if existing_user.id != uid:
                    raise HTTPException(status_code=400, detail="Username already exists")

        # Add update timestamp
        update_data["lasted_update"] = datetime.now(timezone.utc)

        # Update Firestore document
        db.collection("users").document(uid).update(update_data)

        return JSONResponse(status_code=200,
                            content={"message": "User profile updated successfully"})
    except HTTPException:
        raise
    except Exception as e:
        # Log the actual error for debugging
        print(f"Error updating profile: {str(e)}")
        print(f"Error type: {type(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e

@router.put("/users/me/email")
async def change_email(email_change: ChangeEmailSchema, 
                       current_user=Depends(get_current_user)):
    """Change user email"""
    try:
        uid = current_user["uid"]
        new_email = email_change.new_email

        # Update email in Firebase Authentication
        auth.update_user(uid, email=new_email)
        # Update email in Firestore
        db.collection("users").document(uid).update({
            "email": new_email,
            "lasted_update": datetime.now(timezone.utc)
        })
        return JSONResponse(status_code=200,
                            content={"message": "Email updated successfully"})
    except auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Email already in use") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.put("/users/me/password")
async def change_password(password_change: ChangePasswordSchema, 
                          current_user=Depends(get_current_user)):
    """Change user password"""
    try:
        uid = current_user["uid"]
        new_password = password_change.new_password

        # Update password in Firebase Authentication
        auth.update_user(uid, password=new_password)
        return JSONResponse(status_code=200,
                            content={"message": "Password updated successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

def require_admin(user=Depends(get_current_user)):
    """Dependency to ensure the current user is an admin"""
    try:
        uid = user["uid"]
        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            raise HTTPException(404, "User not found")
        user_data = doc.to_dict()
        if not user_data or user_data.get("role") != "admin":
            raise HTTPException(403, "Admin access required")
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in require_admin: {str(e)}")
        raise HTTPException(500, f"Error checking admin status: {str(e)}") from e

@router.get("/users")
async def list_all_users(admin_user=Depends(require_admin)):
    """List all users (admin only)"""
    try:
        users_ref = db.collection("users")
        users = []

        for doc in users_ref.stream():
            try:
                user_data = doc.to_dict()
                # Validate and convert to UserSchema to ensure data integrity
                user = UserSchema(**user_data)
                # Convert back to dict with proper serialization
                users.append(user.model_dump(mode='json'))
            except Exception as e:
                # Log error but continue with other users
                print(f"Error processing user {doc.id}: {str(e)}")
                continue

        return JSONResponse(status_code=200,
                            content={"users": users})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e

@router.post("/auth/logout")
async def logout_user(current_user=Depends(get_current_user)):
    """Logout user (token revocation)"""
    try:
        uid = current_user["uid"]
        # Revoke all refresh tokens for a specified user
        auth.revoke_refresh_tokens(uid)
        return JSONResponse(status_code=200,
                            content={"message": "User logged out successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
