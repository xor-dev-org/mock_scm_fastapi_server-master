from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "mock-secret-key"
ALGORITHM = "HS256"

def create_token(user):
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "name": user["name"],
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)