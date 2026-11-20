# from fastapi import Depends, HTTPException, status
# from fastapi.security import (
#     HTTPBearer,
#     HTTPAuthorizationCredentials,
# )
# from jose import JWTError, jwt
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import settings
# from app.db.database import get_db
# from app.db.models.user_details import UserDetails

# security = HTTPBearer()


# async def get_current_user(
#     credentials: HTTPAuthorizationCredentials = Depends(security),
#     db: AsyncSession = Depends(get_db),
# ) -> UserDetails:

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials.",
#         headers={
#             "WWW-Authenticate": "Bearer",
#         },
#     )

#     token = credentials.credentials

#     try:
#         payload = jwt.decode(
#             token,
#             settings.JWT_SECRET_KEY,
#             algorithms=[settings.JWT_ALGORITHM],
#         )

#         user_id = payload.get("sub")

#         if user_id is None:
#             raise credentials_exception

#         user_id = int(user_id)

#     except (JWTError, ValueError):
#         raise credentials_exception

#     result = await db.execute(
#         select(UserDetails).where(
#             UserDetails.id == user_id,
#             UserDetails.is_active.is_(True),
#         )
#     )

#     user = result.scalar_one_or_none()

#     if user is None:
#         raise credentials_exception

#     return user


from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.clients.auth import get_auth_user

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    device_fingerprint: str | None = Header(
        default=None,
        alias="X-Device-Fingerprint",
    ),
    db: AsyncSession = Depends(get_db),
) -> UserDetails:

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not x_user_id or not device_fingerprint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id and X-Device-Fingerprint headers are required.",
        )

    auth_data = await get_auth_user(
        token=credentials.credentials,
        user_id=x_user_id,
        device_fingerprint=device_fingerprint,
    )

    auth_user = auth_data["user"]
    profile = auth_data.get("profile") or {}

    auth_user_id = str(auth_user["id"])
    email = auth_user["email"]

    # First, find the user using the Auth Service UUID.
    result = await db.execute(
        select(UserDetails).where(UserDetails.auth_user_id == auth_user_id)
    )
    user = result.scalar_one_or_none()

    # If not found, try mapping an existing local user by email.
    if user is None:
        result = await db.execute(select(UserDetails).where(UserDetails.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.auth_user_id = auth_user_id

    # If this is a new Auth Service user, create a local record.
    if user is None:
        user = UserDetails(
            auth_user_id=auth_user_id,
            email=email,
            first_name=profile.get("first_name"),
            last_name=profile.get("last_name"),
            is_active=True,
        )
        db.add(user)

    else:
        # Keep basic profile information synchronized.
        user.email = email
        # user.first_name = profile.get("first_name")
        # user.last_name = profile.get("last_name")
        if profile.get("first_name") is not None:
            user.first_name = profile["first_name"]

        if profile.get("last_name") is not None:
            user.last_name = profile["last_name"]

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your AI Calling account is inactive.",
        )

    await db.commit()
    await db.refresh(user)

    return user
