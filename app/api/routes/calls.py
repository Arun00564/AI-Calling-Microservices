from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, Query, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.start_call import StartCallRequest
from app.schemas.bulk_call import BulkCallRequest
from app.services.voice_call import VoiceCallService
from app.db.models.user_details import UserDetails
from app.api.dependencies import get_current_user

from app.services.call_history import CallHistoryService

router = APIRouter(
    prefix="/api/v1/calls",
    tags=["Calls"],
)


@router.post("/start")
async def start_call(
    request: StartCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = VoiceCallService(db=db, current_user=current_user)

    result = await service.start_call(
        agent_id=request.agent_id,
        customer_id=request.customer_id,
        call_data=request.payload,
        organisation_id=request.organisation_id,
        product_id=request.product_id,
        feature_id=request.feature_id,
    )

    return {
        "status": 200,
        "message": "Voice call initiated successfully.",
        "success": True,
        "data": result,
    }


@router.post("/bulk")
async def manual_bulk_calls(
    request: BulkCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.manual_bulk_calls(
        agent_id=request.agent_id,
        leads=request.leads,
        organisation_id=request.organisation_id,
        product_id=request.product_id,
        feature_id=request.feature_id,
    )

    return {
        "status": 200,
        "message": "Manual bulk voice calls scheduled successfully.",
        "success": True,
        "data": result,
    }


@router.get("/excel-columns/")
async def get_excel_columns(
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_excel_columns()

    return {
        "status": 200,
        "message": "Excel columns fetched successfully.",
        "success": True,
        "data": result,
    }


@router.post("/bulk-voice-call/{agent_id}/upload-excel/")
async def bulk_calling_upload_excel_and_initiate_calls(
    agent_id: int,
    lead_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.bulk_calling_upload_excel_and_initiate_calls(
        agent_id=agent_id,
        excel_file=lead_file,
    )

    return {
        "status": 200,
        "message": "Bulk calling started.",
        "success": True,
        "data": result,
    }


@router.get("/bulk-voice-call/{agent_id}/download-sample-excel/")
async def download_sample_excel(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    return await service.download_sample_excel(agent_id=agent_id)


@router.get("/history")
async def get_call_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    period: str | None = Query("7days"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    status: str | None = Query(None),
    agent_id: int | None = Query(None),
    direction: str | None = Query(None),
    customer_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = CallHistoryService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_call_history(
        page=page,
        page_size=page_size,
        search=search,
        period=period,
        start_date=start_date,
        end_date=end_date,
        status=status,
        agent_id=agent_id,
        direction=direction,
        customer_id=customer_id,
    )

    return {
        "status": 200,
        "success": True,
        "message": "Call history fetched successfully.",
        "data": result,
    }


@router.get("/history/{call_log_id}")
async def get_call_details(
    call_log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = CallHistoryService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_call_details(
        call_log_id=call_log_id,
    )

    return {
        "status": 200,
        "success": True,
        "message": "Call details fetched successfully.",
        "data": result,
    }


@router.get("/{flow_run_uuid}")
async def get_call_details(
    flow_run_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_call_details(
        flow_run_uuid=flow_run_uuid,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Voice call not found.",
        )

    return {
        "success": True,
        "message": "Voice call details fetched successfully.",
        "data": result,
    }
