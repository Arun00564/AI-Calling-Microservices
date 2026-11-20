import httpx

from fastapi import HTTPException, status

from app.core.config import settings


async def get_auth_user(
    token: str,
    user_id: str,
    device_fingerprint: str,
) -> dict:

    url = (
        f"{settings.AUTH_SERVICE_URL.rstrip('/')}"
        f"{settings.AUTH_SERVICE_API_PREFIX.rstrip('/')}"
        "/users/me"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Id": user_id,
        "X-Device-Fingerprint": device_fingerprint,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.AUTH_SERVICE_TIMEOUT) as client:

            response = await client.get(url, headers=headers)

        if response.status_code in (401, 403, 404):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if response.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is unavailable.",
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected response from authentication service.",
            )

        data = response.json()

        auth_user = data.get("user")

        if not isinstance(auth_user, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid authentication service response.",
            )

        if (
            not auth_user.get("id")
            or str(auth_user["id"]) != user_id
            or not auth_user.get("email")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authenticated user.",
            )

        return data

    except HTTPException:
        raise

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timed out.",
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to authentication service.",
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid JSON response from authentication service.",
        )
