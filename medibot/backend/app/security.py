import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Header, HTTPException
from .config import DEMO_USERS
SECRET = os.getenv("JWT_SECRET", "development-only-change-this-secret")
ALGORITHM = "HS256"
def authenticate(username: str, password: str):
    user = DEMO_USERS.get(username)
    if not user or user[0] != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    role = user[1]
    token = jwt.encode({"sub": username, "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "480")))}, SECRET, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "username": username, "role": role}
def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please log in to use MediBot")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], SECRET, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role not in {"doctor", "nurse", "billing_executive", "technician", "admin"}: raise ValueError()
        return {"username": payload.get("sub"), "role": role}
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
