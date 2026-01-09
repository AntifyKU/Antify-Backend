from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi import APIRouter
from app.models.user import SignUpSchema, LoginSchema, UserSchema

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth, firestore
from app.firebase import firebase
import requests

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
        # Return success response
        return JSONResponse(status_code=201, content={"message": "User created successfully"})
    except auth.EmailAlreadyExistsError as exc: # Handle email already exists error
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
            "last_login": datetime.now(timezone.utc)
        })
        return {
            "message": "Login successful",
            "user_id": firebase_user.uid,
            "id_token": user_cred["idToken"],   # Return the ID token for client-side use
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
