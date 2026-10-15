"""Firebase Authentication verification service utilizing Firebase Admin SDK."""

import json
import logging
import os
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger("app.services.firebase_auth")
settings = get_settings()

_firebase_app_initialized = False


def initialize_firebase() -> Optional[firebase_admin.App]:
    """Initialize Firebase Admin SDK with service account credentials."""
    global _firebase_app_initialized
    if _firebase_app_initialized:
        return firebase_admin.get_app()

    cred = None
    # 1. Local JSON file path
    if settings.firebase_credentials_path and os.path.exists(settings.firebase_credentials_path):
        try:
            cred = credentials.Certificate(settings.firebase_credentials_path)
            logger.info("Initializing Firebase Admin with certificate file: %s", settings.firebase_credentials_path)
        except Exception as exc:
            logger.error("Failed to load Firebase credentials from file: %s", type(exc).__name__)

    # 2. Raw JSON string from environment variable (useful on Render/Cloud)
    elif settings.firebase_credentials_json:
        try:
            cred_dict = json.loads(settings.firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
            logger.info("Initializing Firebase Admin with inline JSON credentials")
        except Exception as exc:
            logger.error("Failed to parse Firebase credentials JSON: %s", type(exc).__name__)

    # 3. Project ID without service account (fallback or mock)
    options = {}
    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id

    try:
        if cred:
            app = firebase_admin.initialize_app(cred, options=options)
        else:
            # Attempt default application credentials
            app = firebase_admin.initialize_app(options=options)
        _firebase_app_initialized = True
        logger.info("Firebase Admin initialized successfully")
        return app
    except Exception as exc:
        logger.warning("Could not initialize Firebase Admin SDK: %s", exc)
        return None


def verify_firebase_id_token(id_token: str) -> Dict[str, Any]:
    """Verify a client-supplied Firebase ID token and extract user claims.
    
    Raises HTTPException(401) on invalid, expired, or malformed tokens.
    """
    if not _firebase_app_initialized:
        initialize_firebase()

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # verify_id_token validates signature, issuer, audience, and expiration
        decoded_token = auth.verify_id_token(id_token, check_revoked=False)
        return decoded_token
    except auth.ExpiredIdTokenError:
        logger.warning("Firebase token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.RevokedIdTokenError:
        logger.warning("Firebase token revoked")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError as exc:
        logger.warning("Invalid Firebase token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Unexpected error during Firebase token verification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
