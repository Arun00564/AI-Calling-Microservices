from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.db.models.user_details import UserDetails

router = APIRouter(
    prefix="/test",
    tags=["Test"],
)


@router.get("/me")
async def get_me(
    current_user: UserDetails = Depends(get_current_user),
):
    print(f"Current user----: {current_user}")
    return {
        "success": True,
        "user_id": current_user.id,
        "auth_user_id": current_user.auth_user_id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
    }
