from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.api.dependencies import get_current_user

from app.schemas.campaign import CreateCampaignRequest
from app.services.campaign import CampaignService

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaigns"],
)


@router.post("/")
async def create_campaign(
    request: CreateCampaignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = CampaignService(
        db=db,
        current_user=current_user,
    )

    try:
        result = await service.create_campaign(request)

        return {
            "status": 201,
            "success": True,
            "message": "Campaign created successfully.",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to create campaign.",
        )
