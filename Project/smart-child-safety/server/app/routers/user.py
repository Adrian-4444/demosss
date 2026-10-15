"""API Router for User Profile and Family Management."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.child import ChildProfile
from app.models.user import Family, FamilyMembership, UserProfile, utc_now
from app.schemas.user import (
    ChildSummaryItem,
    ChildUpdate,
    FamilyCreate,
    FamilyMembershipItem,
    UserProfileDetailResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.security import (
    AuthenticatedPrincipal,
    get_current_principal,
    verify_guardian_child_access,
    verify_guardian_family_access,
)

router = APIRouter(prefix="/me", tags=["User & Profile"])
family_router = APIRouter(prefix="/families", tags=["Families"])



class ChildCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=64)
    last_name: str | None = Field(None, max_length=64)
    display_name: str | None = Field(None, max_length=120)
    gender: str | None = Field(None, max_length=32)
    sharing_enabled: bool = True


@router.get(
    "",
    response_model=UserProfileDetailResponse,
    summary="Get Authenticated User Profile",
    description="Retrieve the caller's profile, associated families, and linked children.",
)
def get_my_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    user = db.query(UserProfile).filter(UserProfile.id == principal.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")

    memberships = (
        db.query(FamilyMembership, Family)
        .join(Family, Family.id == FamilyMembership.family_id)
        .filter(FamilyMembership.user_id == user.id)
        .all()
    )

    family_items: List[FamilyMembershipItem] = []
    family_ids = []
    for m, f in memberships:
        family_items.append(
            FamilyMembershipItem(
                family_id=f.id,
                family_name=f.name,
                role=m.role,
                created_at=m.created_at,
            )
        )
        family_ids.append(f.id)

    # Fetch children in user's families
    children_records = (
        db.query(ChildProfile)
        .filter(ChildProfile.family_id.in_(family_ids), ChildProfile.deleted_at.is_(None))
        .all()
        if family_ids
        else []
    )

    child_items = [
        ChildSummaryItem(
            id=c.id,
            family_id=c.family_id,
            first_name=c.first_name,
            last_name=c.last_name,
            display_name=c.display_name,
            gender=c.gender,
            sharing_enabled=c.sharing_enabled,
            created_at=c.created_at,
        )
        for c in children_records
    ]

    return UserProfileDetailResponse(
        profile=UserProfileResponse.model_validate(user),
        families=family_items,
        children=child_items,
    )


@router.patch(
    "",
    response_model=UserProfileResponse,
    summary="Update Authenticated User Profile",
    description="Update permitted profile fields (display name, phone number).",
)
def update_my_profile(
    payload: UserProfileUpdate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    user = db.query(UserProfile).filter(UserProfile.id == principal.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number.strip()

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate/Delete User Account",
    description="Deactivate the caller's account and revoke active sessions (GDPR / right-to-be-forgotten).",
)
def delete_my_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    user = db.query(UserProfile).filter(UserProfile.id == principal.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")

    user.is_active = False
    user.disabled_at = utc_now()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@family_router.post(

    "",
    response_model=FamilyMembershipItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create Family Group",
    description="Create a new family group and assign the caller as owner.",
)
def create_family(
    payload: FamilyCreate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    family = Family(name=payload.name.strip(), created_by_user_id=principal.id)
    db.add(family)
    db.flush()

    membership = FamilyMembership(
        family_id=family.id,
        user_id=principal.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    db.refresh(family)

    return FamilyMembershipItem(
        family_id=family.id,
        family_name=family.name,
        role=membership.role,
        created_at=membership.created_at,
    )


@family_router.post(
    "/{family_id}/children",
    response_model=ChildSummaryItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create Child Profile in Family",
    description="Add a child profile under an authorized family.",
)
def create_child_profile(
    family_id: str,
    payload: ChildCreate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    verify_guardian_family_access(
        family_id=family_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    display_name = payload.display_name or payload.first_name
    child = ChildProfile(
        family_id=family_id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip() if payload.last_name else None,
        display_name=display_name.strip(),
        gender=payload.gender,
        sharing_enabled=payload.sharing_enabled,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    return ChildSummaryItem(
        id=child.id,
        family_id=child.family_id,
        first_name=child.first_name,
        last_name=child.last_name,
        display_name=child.display_name,
        gender=child.gender,
        sharing_enabled=child.sharing_enabled,
        created_at=child.created_at,
    )


@family_router.patch(
    "/{family_id}/children/{child_id}",
    response_model=ChildSummaryItem,
    summary="Update Child Profile Settings",
    description="Update child profile settings such as display name, gender, or location sharing state.",
)
def update_child_profile(
    family_id: str,
    child_id: str,
    payload: ChildUpdate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    verify_guardian_family_access(
        family_id=family_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    child = (
        db.query(ChildProfile)
        .filter(
            ChildProfile.id == child_id,
            ChildProfile.family_id == family_id,
            ChildProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child profile not found")

    if payload.first_name is not None:
        child.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        child.last_name = payload.last_name.strip()
    if payload.display_name is not None:
        child.display_name = payload.display_name.strip()
    if payload.gender is not None:
        child.gender = payload.gender.strip()
    if payload.sharing_enabled is not None:
        child.sharing_enabled = payload.sharing_enabled
    if payload.location_interval_moving is not None:
        child.location_interval_moving = payload.location_interval_moving
    if payload.location_interval_stationary is not None:
        child.location_interval_stationary = payload.location_interval_stationary

    child.updated_at = utc_now()
    db.commit()
    db.refresh(child)

    return ChildSummaryItem(
        id=child.id,
        family_id=child.family_id,
        first_name=child.first_name,
        last_name=child.last_name,
        display_name=child.display_name,
        gender=child.gender,
        sharing_enabled=child.sharing_enabled,
        created_at=child.created_at,
    )


@family_router.delete(
    "/{family_id}/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Child Profile (Right to be Forgotten)",
    description=(
        "Permanently delete a child profile and cascade-purge all associated tracking data "
        "(GPS records, latest location, paired devices, safety events, and commands)."
    ),
)
def delete_child_profile(
    family_id: str,
    child_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    verify_guardian_family_access(
        family_id=family_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    child = (
        db.query(ChildProfile)
        .filter(
            ChildProfile.id == child_id,
            ChildProfile.family_id == family_id,
        )
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child profile not found")

    db.delete(child)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

