import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.auth.models import User, UserRole
from backend.app.modules.auth.security.hashing import hash_password


async def main() -> None:
    username = (settings.nexusops_admin_user or "").strip().lower()
    email = (settings.nexusops_admin_email or "").strip().lower()
    password = settings.nexusops_admin_password or ""

    if not username or not email or not password:
        raise SystemExit(
            "Missing NEXUSOPS_ADMIN_USER, NEXUSOPS_ADMIN_EMAIL, or NEXUSOPS_ADMIN_PASSWORD."
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            action = "created"
        else:
            user.username = username
            user.email = email
            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_superuser = True
            action = "updated"

        await session.commit()
        print(f"Bootstrap admin {action}: username={username} email={email}")


if __name__ == "__main__":
    asyncio.run(main())
