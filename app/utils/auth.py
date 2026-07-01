import os
from typing import Dict

from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Missing required environment variable: SECRET_KEY")
ALGORITHM = "HS256"

def create_token(user):
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "name": user["name"], 
        "email": user["email"],
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def extract_bearer_token(authorization_header: str) -> str:
    if not authorization_header:
        raise JWTError("Missing Authorization header")

    scheme, _, token = authorization_header.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise JWTError("Invalid Authorization header format")

    return token