from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi import APIRouter
from app.models.user import SignUpSchema, UserSchema

from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import auth, firestore
from app.firebase import firebase

router = APIRouter()
db = firestore.client()

@router.post("/auth/signup")
async def create_new_account(user: SignUpSchema):
    """Create a new user account"""
    username = user.username
    email = user.email
    password = user.password

    try:
        # Create user in Firebase Authentication
        firebase_user = auth.create_user(display_name=username, email=email, password=password)
        # Add user to Firestore
        user_data = UserSchema(
            user_id=firebase_user.uid,
            username=username,
            email=email,
            created_at=datetime.now(ZoneInfo("Asia/Bangkok"))
        )
        db.collection("users").document(firebase_user.uid).set(
            user_data.model_dump()
        )
        # Return success response
        return JSONResponse(status_code=201, content={"message": "User created successfully"})
    except auth.EmailAlreadyExistsError as exc: # Handle email already exists error
        raise HTTPException(status_code=400, detail="Email already exists") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
