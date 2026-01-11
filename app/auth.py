import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Header, HTTPException
from jose import jwt

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

def verify_token(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise Exception()
        jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
