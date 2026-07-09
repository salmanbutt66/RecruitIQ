import re
import uuid
from datetime import UTC, datetime

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SubscriptionPlan, UserRole
from app.db.models import AuditLog, Organization, Subscription, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "org"


async def create_audit_log(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


async def register_organization(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    organization_name: str,
) -> tuple[Organization, User]:
    base_slug = slugify(organization_name)
    slug = base_slug
    counter = 1
    while True:
        existing = await db.execute(select(Organization).where(Organization.slug == slug))
        if existing.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(name=organization_name, slug=slug)
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.ORG_ADMIN.value,
    )
    db.add(user)

    subscription = Subscription(
        organization_id=org.id,
        plan=SubscriptionPlan.STARTER.value,
        status="active",
        usage_period_start=datetime.now(UTC),
    )
    db.add(subscription)
    await db.flush()
    return org, user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower(), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_org_user_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(User).where(User.organization_id == organization_id)
    )
    return result.scalar_one()
