"""
FastAPI dependency for Firebase ID-token authentication.

Usage:
    from auth_middleware import get_current_user, require_admin

    @router.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        ...
"""
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from firebase_admin import auth as fb_auth

_bearer = HTTPBearer(auto_error=False)

# Comma-separated list of Firebase UIDs that have platform-admin access.
# Example: ADMIN_UIDS=uid1,uid2
ADMIN_UIDS: set = {
    uid.strip()
    for uid in os.getenv("ADMIN_UIDS", "").split(",")
    if uid.strip()
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Verify the Firebase ID token in the Authorization: Bearer header.
    Returns the decoded token dict (includes uid, email, etc.).
    Raises HTTP 401 if missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    try:
        return fb_auth.verify_id_token(credentials.credentials, check_revoked=False)
    except fb_auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """
    Restrict endpoint access to platform admin UIDs (ADMIN_UIDS env var).
    Raises HTTP 503 if ADMIN_UIDS is not configured.
    Raises HTTP 403 if the authenticated user is not an admin.
    """
    if not ADMIN_UIDS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access not configured. Set ADMIN_UIDS environment variable.",
        )
    if user.get("uid") not in ADMIN_UIDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user
