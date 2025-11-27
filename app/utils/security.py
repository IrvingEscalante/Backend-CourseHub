from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
import base64
from fastapi import Depends, Header
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: int | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_delta if expires_delta else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SECRET_KEY_EMAIL = b"clave-secreta123"  # Debe ser de 16, 24 o 32 bytes

def encrypt_email(email: str) -> str:
    cipher = AES.new(SECRET_KEY_EMAIL, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(email.encode('utf-8'), AES.block_size))
    return base64.urlsafe_b64encode(encrypted).decode('utf-8')

def decrypt_email(token: str) -> str:
    cipher = AES.new(SECRET_KEY_EMAIL, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(base64.urlsafe_b64decode(token)), AES.block_size)
    return decrypted.decode('utf-8')

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if authorization is None:
        return None
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            return None
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except JWTError:
        return None