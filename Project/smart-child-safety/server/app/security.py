"""Security module: Firebase token authentication, principal extraction, and relationship authorization."""

import hashlib
import hmac
import logging
import secrets
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.child import ChildProfile, RegisteredDevice
from app.models.user import FamilyMembership, UserProfile
from app.services import firebase_auth

logger = logging.getLogger("app.security")

# HTTP Bearer scheme
bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)


class CallerIdentity(BaseModel):
    """Represents an authenticated caller submitting location or telemetry."""

    caller_type: str  # "device" or "guardian"
    device_id: Optional[str] = None
    device_identifier: Optional[str] = None
    user_id: Optional[str] = None
    child_id: str


class AuthenticatedPrincipal(BaseModel):
    """Represents a verified caller derived from a cryptographic Firebase ID token."""

    id: str  # UserProfile database UUID
    firebase_uid: str  # Verified Firebase UID claim
    email: str
    display_name: Optional[str] = None
    role: str = "guardian"  # guardian | operator
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


def hash_pairing_code(code: str, salt: str = "smart_child_safety_salt") -> str:
    """Compute an HMAC-SHA256 hash of a pairing invitation code.
    
    Raw pairing codes are never persisted to disk or databases.
    """
    return hmac.new(
        salt.encode("utf-8"),
        code.strip().upper().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_pairing_code(length: int = 6) -> str:
    """Generate a high-entropy, human-friendly uppercase alphanumeric pairing code."""
    # Exclude ambiguous characters (0, O, 1, I) to prevent parent/child entry errors
    charset = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(secrets.choice(charset) for _ in range(length))


def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    """Validate Firebase ID token and retrieve/provision the corresponding UserProfile.
    
    Derives identity exclusively from verified token claims (uid), never from request bodies.
    """
    token = credentials.credentials
    decoded_token = firebase_auth.verify_firebase_id_token(token)

    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decoded_token.get("email") or f"{firebase_uid}@firebase.user"
    display_name = decoded_token.get("name")

    # Fetch or auto-provision UserProfile on first authenticated request
    user = db.query(UserProfile).filter(UserProfile.firebase_uid == firebase_uid).first()
    if not user:
        logger.info("Auto-provisioning first-time profile for firebase_uid=%s", firebase_uid)
        user = UserProfile(
            firebase_uid=firebase_uid,
            email=email,
            display_name=display_name,
            role="guardian",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active or user.disabled_at is not None:
        logger.warning("Access denied for disabled user id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or disabled",
        )

    return AuthenticatedPrincipal(
        id=user.id,
        firebase_uid=user.firebase_uid,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


def verify_guardian_family_access(
    family_id: str,
    principal: AuthenticatedPrincipal,
    db: Session,
    allowed_roles: Optional[List[str]] = None,
) -> FamilyMembership:
    """Verify that the principal is an active member of the specified family."""
    membership = (
        db.query(FamilyMembership)
        .filter(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == principal.id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have an active membership in this family",
        )

    if allowed_roles and membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Insufficient role permissions (requires {allowed_roles})",
        )

    return membership


def verify_guardian_child_access(
    child_profile_id: str,
    principal: AuthenticatedPrincipal,
    db: Session,
    allowed_roles: Optional[List[str]] = None,
) -> ChildProfile:
    """Verify that the principal is authorized to access the specified child profile.
    
    Enforces that the caller belongs to the family owning the child profile.
    """
    child = db.query(ChildProfile).filter(ChildProfile.id == child_profile_id).first()
    if not child or child.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child profile not found",
        )

    # Check that guardian has membership in child's family
    verify_guardian_family_access(
        family_id=child.family_id,
        principal=principal,
        db=db,
        allowed_roles=allowed_roles,
    )

    return child


def verify_child_ingestion_auth(
    child_id: str,
    request: Request,
    db: Session,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> CallerIdentity:
    """Authenticate and authorize caller for child-scoped telemetry or location ingestion.

    Accepts either:
    1. Paired child device via `X-Device-Identifier` header (verified against registered_devices).
    2. Authorized guardian via Bearer token (verified via Firebase Auth + FamilyMembership).
    """
    x_device_identifier = request.headers.get("X-Device-Identifier")

    if x_device_identifier:
        clean_identifier = x_device_identifier.strip()
        device = (
            db.query(RegisteredDevice)
            .filter(RegisteredDevice.device_identifier == clean_identifier)
            .first()
        )
        if not device or not device.is_active:
            logger.warning("Rejected ingestion from invalid/inactive device_identifier=%s", clean_identifier)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or deactivated device identifier",
            )
        if device.child_profile_id != child_id:
            logger.warning("Device id=%s attempted unauthorized upload to mismatch child_id=%s", device.id, child_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device is not authorized for this child profile",
            )
        return CallerIdentity(
            caller_type="device",
            device_id=device.id,
            device_identifier=device.device_identifier,
            child_id=child_id,
        )

    # If no X-Device-Identifier, verify Bearer token
    token = credentials.credentials if credentials else None
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if token:
        decoded_token = firebase_auth.verify_firebase_id_token(token)
        firebase_uid = decoded_token.get("uid")
        if not firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject identifier",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.query(UserProfile).filter(UserProfile.firebase_uid == firebase_uid).first()
        if not user or not user.is_active or user.disabled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated or disabled",
            )
        principal = AuthenticatedPrincipal(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
        )
        verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)
        return CallerIdentity(
            caller_type="guardian",
            user_id=principal.id,
            child_id=child_id,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: Provide a valid X-Device-Identifier header or Bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
