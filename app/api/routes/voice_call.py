from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.api.dependencies import get_current_user

from app.schemas.voice_call import StartCallRequest
from app.services.voice_call import VoiceCallService

router = APIRouter(
    prefix="/api/v1/voice-agents",
    tags=["Voice Calling"],
)


@router.post("/{agent_id}/start-call")
async def start_call(
    agent_id: int,
    request: StartCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.start_call(
        agent_id=agent_id,
        customer_id=request.customer_id,
        call_data=request.call_data,
        organisation_id=request.organisation_id,
        product_id=request.product_id,
        feature_id=request.feature_id,
        knowledge_base_id=request.knowledge_base_id,
        context=request.context,
    )

    return {
        "status": 200,
        "message": "Voice call initiated successfully.",
        "success": True,
        "data": result,
    }
