import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.core.security import security
from app.db.models import User
from app.db.session import get_db
from app.schemas import (
    InviteUserRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_audit_log,
    get_org_user_count,
    hash_password,
    register_organization,
)
from app.services.subscription_service import check_user_quota
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org, user = await register_organization(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        organization_name=body.organization_name,
    )
    await create_audit_log(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="register",
        entity_type="user",
        entity_id=str(user.id),
    )
    access = security.create_access_token(uid=str(user.id), data={"role": user.role})
    refresh = security.create_refresh_token(uid=str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = security.create_access_token(uid=str(user.id), data={"role": user.role})
    refresh = security.create_refresh_token(uid=str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return user


@router.post("/invite", response_model=UserResponse)
async def invite_user(
    body: InviteUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    count = await get_org_user_count(db, current.organization_id)
    await check_user_quota(db, current.organization_id, count)

    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        organization_id=current.organization_id,
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await create_audit_log(
        db,
        organization_id=current.organization_id,
        user_id=current.id,
        action="user_invited",
        entity_type="user",
        entity_id=str(user.id),
        details={"role": body.role},
    )
    await db.flush()
    return user
