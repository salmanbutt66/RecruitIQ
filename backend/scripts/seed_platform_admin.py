"""Seed a platform admin user for the admin portal."""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.enums import SubscriptionPlan, UserRole
from app.db.models import Organization, Subscription, User
from app.db.session import AsyncSessionLocal
from app.services.auth_service import hash_password, slugify


async def seed_platform_admin() -> None:
    email = os.environ.get("PLATFORM_ADMIN_EMAIL", "admin@recruitiq.local").lower()
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "changeme123")
    full_name = os.environ.get("PLATFORM_ADMIN_NAME", "Platform Admin")
    org_name = os.environ.get("PLATFORM_ORG_NAME", "RecruitIQ Platform")

    async with AsyncSessionLocal() as db:
        existing_user = await db.execute(select(User).where(User.email == email))
        if existing_user.scalar_one_or_none():
            print(f"Platform admin already exists: {email}")
            return

        slug = slugify(org_name)
        existing_org = await db.execute(select(Organization).where(Organization.slug == slug))
        org = existing_org.scalar_one_or_none()

        if org is None:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            await db.flush()

            subscription = Subscription(
                organization_id=org.id,
                plan=SubscriptionPlan.ENTERPRISE.value,
                status="active",
            )
            db.add(subscription)

        user = User(
            organization_id=org.id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.PLATFORM_ADMIN.value,
        )
        db.add(user)
        await db.commit()

        print("Platform admin created successfully.")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print("  Admin UI: http://localhost:3001/login")


def main() -> None:
    try:
        asyncio.run(seed_platform_admin())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
