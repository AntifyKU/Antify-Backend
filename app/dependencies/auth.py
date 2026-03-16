""" Firebase authentication utilities """
from typing import Annotated
from fastapi import Header, HTTPException, Depends
from firebase_admin import auth, firestore

BEARER_PREFIX = "Bearer "
INVALID_TOKEN_DETAIL = "Invalid token"
TOKEN_EXPIRED_DETAIL = "Token expired"
TOKEN_REVOKED_DETAIL = "Token revoked. Please log in again."
AUTHENTICATION_FAILED_DETAIL = "Authentication failed"


def _verify_firebase_token(token: str) -> dict:
    """Verify a Firebase ID token"""
    try:
        # clock_skew_seconds gives a small grace window for clock drift
        # between the mobile device and Firebase servers.
        decoded = auth.verify_id_token(token, clock_skew_seconds=10)
        return decoded

    except auth.ExpiredIdTokenError as exc:
        # Token is structurally valid but has passed its exp claim.
        # Frontend should attempt a silent refresh with the refresh_token.
        raise HTTPException(
            status_code=401,
            detail=TOKEN_EXPIRED_DETAIL,
        ) from exc

    except auth.RevokedIdTokenError as exc:
        # Token was explicitly revoked (e.g. after logout / password change).
        # Frontend must force the user to log in again.
        raise HTTPException(
            status_code=401,
            detail=TOKEN_REVOKED_DETAIL,
        ) from exc

    except auth.InvalidIdTokenError as exc:
        # Malformed token, wrong audience, bad signature, etc.
        raise HTTPException(
            status_code=401,
            detail=INVALID_TOKEN_DETAIL,
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=AUTHENTICATION_FAILED_DETAIL,
        ) from exc


def verify_token(authorization: str = Header(...)) -> dict:
    """Dependency: verify Firebase ID token from Authorization header"""
    if not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail=INVALID_TOKEN_DETAIL)
    token = authorization.removeprefix(BEARER_PREFIX).strip()
    return _verify_firebase_token(token)


def get_current_user(authorization: str = Header(...)) -> dict:
    """Dependency: return the decoded Firebase token for the current user"""
    if not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail=INVALID_TOKEN_DETAIL)
    token = authorization.removeprefix(BEARER_PREFIX).strip()
    return _verify_firebase_token(token)

def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Dependency: verify the calling user has the 'admin' role"""
    try:
        db = firestore.client()
        doc = db.collection("users").document(current_user["uid"]).get()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error checking admin status",
        ) from exc

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    if doc.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return current_user
