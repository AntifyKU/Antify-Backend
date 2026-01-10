from fastapi import Header, HTTPException
from firebase_admin import auth

def verify_token(authorization: str = Header(...)):
    """Verify Firebase ID token from Authorization header"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid token")

    token = authorization.replace("Bearer ", "")
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired token") from exc

def get_current_user(authorization: str = Header(...)):
    """Dependency to get current user from Authorization header"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]
    try:
        decoded = auth.verify_id_token(token)
        return decoded  # Return decoded token with user info
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
