import logfire
from authx import AuthX, AuthXConfig
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

settings = get_settings()

auth_config = AuthXConfig(
    JWT_SECRET_KEY=settings.jwt_secret,
    JWT_ALGORITHM=settings.jwt_algorithm,
    JWT_ACCESS_TOKEN_EXPIRES=settings.jwt_access_token_expire_minutes * 60,
    JWT_REFRESH_TOKEN_EXPIRES=settings.jwt_refresh_token_expire_days * 86400,
    JWT_TOKEN_LOCATION=["headers"],
)

security = AuthX(config=auth_config)
bearer_scheme = HTTPBearer(auto_error=False)


def configure_logfire() -> None:
    if settings.logfire_token:
        logfire.configure(
            token=settings.logfire_token,
            service_name="recruitiq-api",
            environment=settings.app_env,
        )
    else:
        logfire.configure(
            send_to_logfire="if-token-present",
            service_name="recruitiq-api",
            environment=settings.app_env,
        )


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return security.verify_token(credentials.credentials, verify_type="access")
    except Exception as exc:
        print(f"TOKEN VERIFY FAILED: {type(exc).__name__}: {exc}")  # TEMP DEBUG
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc
