import uuid
from typing import Annotated

from authx import TokenPayload
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserRole
from app.core.security import security
from app.db.models import User
from app.db.session import get_db


async def get_current_user(
    payload: Annotated[TokenPayload, Depends(security.access_token_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user_id = payload.sub
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == uuid.UUID(user_id), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker