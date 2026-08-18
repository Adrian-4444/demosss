import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app import models

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generate JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> dict:
    """Verify JWT access token and return payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def check_brute_force_lockout(user: models.User) -> None:
    """Check if user account is currently locked out."""
    if user.is_locked:
        if user.locked_until and datetime.utcnow() < user.locked_until:
            time_left = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to multiple failed login attempts. Try again in {time_left} minutes."
            )
        else:
            # Lockout expired, auto-unlock
            user.is_locked = False
            user.failed_attempts = 0
            user.locked_until = None

def record_failed_login(user: models.User, db: Session) -> None:
    """Increment failed login attempts and trigger lockout if limit reached."""
    user.failed_attempts += 1
    if user.failed_attempts >= settings.MAX_FAILED_ATTEMPTS:
        user.is_locked = True
        user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
    db.commit()

def reset_failed_login(user: models.User, db: Session) -> None:
    """Reset failed login count upon successful authentication."""
    user.failed_attempts = 0
    user.is_locked = False
    user.locked_until = None
    db.commit()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """FastAPI dependency to retrieve the authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    
    payload = verify_access_token(token)
    if payload is None:
        raise credentials_exception
        
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
        
    if user.is_locked and user.locked_until and datetime.utcnow() < user.locked_until:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is currently locked."
        )
        
    return user

def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """FastAPI dependency to verify if user has admin privileges."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user
