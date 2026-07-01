import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from app.utils.auth import decode_token

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Decodes the JWT and validates the basic payload structure."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
        return payload  # Expected to contain: {"email": "...", "role": "admin"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

class BlockedUsers:
    """Blocks specific users on endpoints."""
    def __init__(self, blocked_users: list[str]):
        self.blocked_users = blocked_users

    def __call__(self, current_user: dict = Depends(get_current_user)):
        email = current_user.get("email")
        if email in self.blocked_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{email}' is not authorized to access this resource."
            )
        return current_user