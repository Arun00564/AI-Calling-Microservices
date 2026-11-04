from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.db.database import get_db
from app.schemas.plivo_webhook import PlivoWebhookPayload
from app.services.plivo_webhook import PlivoWebhookService

router = APIRouter(
    prefix="/webhooks/plivo",
    tags=["Plivo Webhooks"],
)


@router.post("/events")
async def plivo_event_webhook(
    payload: PlivoWebhookPayload,
    db: AsyncSession = Depends(get_db),
):

    service = PlivoWebhookService(
        db=db,
    )

    result = await service.process_event(payload=payload.model_dump())

    if not result["success"]:
        raise HTTPException(
            status_code=result["status"],
            detail=result["message"],
        )

    return result
