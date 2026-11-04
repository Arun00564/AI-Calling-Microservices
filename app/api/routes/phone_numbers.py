from typing import Literal
import httpx
from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.db.models.voice_agent import VoiceAgent
from app.db.models.voice_number import VoiceNumber
from app.schemas.phone_numbers import AssignPhoneNumberRequest
from app.services.voizematic import VoizematicPhoneNumberService

router = APIRouter(
    prefix="/api/v1/phone-numbers",
    tags=["Phone Numbers"],
)


@router.get("/available")
async def get_available_phone_numbers(
    country: str = Query(default="IN", min_length=2, max_length=2),
    number_type: str | None = Query(default=None, alias="type"),
    capabilities: str | None = Query(default="voice"),
    area_code: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoizematicPhoneNumberService()

    result = await service.get_available_numbers(
        country=country,
        number_type=number_type,
        capabilities=capabilities,
        area_code=area_code,
        limit=limit,
    )

    return {
        "success": True,
        "message": "Available phone numbers fetched successfully.",
        "data": result,
    }


@router.get("/my-numbers")
async def get_my_phone_numbers(
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # for getting all the voice numbers of the current user, we can use the following code snippet:

    # result = await db.execute(
    #     select(VoiceNumber)
    #     .where(
    #         VoiceNumber.user_id == current_user.id,
    #         VoiceNumber.is_active.is_(True),
    #     )
    #     .order_by(VoiceNumber.created_at.desc())
    # )

    result = await db.execute(
        select(VoiceNumber)
        .where(
            VoiceNumber.user_id == current_user.id,
            VoiceNumber.provider == "voizematic",
            VoiceNumber.is_active.is_(True),
        )
        .order_by(VoiceNumber.created_at.desc())
    )

    numbers = result.scalars().all()

    return {
        "success": True,
        "message": "Phone numbers retrieved successfully",
        "data": [
            {
                "id": number.id,
                "phone_number": number.phone_number,
                "provider": number.provider,
                "provider_number_id": number.provider_number_id,
                "is_active": number.is_active,
                "created_at": number.created_at,
            }
            for number in numbers
        ],
    }


@router.get("/my-numbers/{number_id}")
async def get_my_number_details(
    number_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    result = await db.execute(
        select(VoiceNumber).where(
            VoiceNumber.id == number_id,
            VoiceNumber.user_id == current_user.id,
            VoiceNumber.provider == "voizematic",
        )
    )

    number = result.scalar_one_or_none()

    if number is None:
        raise HTTPException(
            status_code=404,
            detail="Voizematic phone number not found",
        )

    service = VoizematicPhoneNumberService()

    try:
        details = await service.get_number_details(
            number.provider_number_id or number.phone_number
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": "Phone number details retrieved successfully",
        "data": details,
    }


async def get_agents(self):
    url = f"{self.BASE_URL}/agents"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            headers=self.headers,
        )

    if response.is_error:
        raise RuntimeError(
            f"Voizematic API error: {response.status_code} - {response.text}"
        )

    return response.json()


@router.put("/my-numbers/{number_id}/agent")
async def assign_number_to_agent(
    number_id: int,
    request: AssignPhoneNumberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # Get user's Voizematic number
    number_result = await db.execute(
        select(VoiceNumber).where(
            VoiceNumber.id == number_id,
            VoiceNumber.user_id == current_user.id,
            VoiceNumber.provider == "voizematic",
            VoiceNumber.is_active.is_(True),
        )
    )

    number = number_result.scalar_one_or_none()

    if not number:
        raise HTTPException(
            status_code=404,
            detail="Voizematic phone number not found",
        )

    # Get user's VoiceAgent
    agent_result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == request.voice_agent_id,
            VoiceAgent.user_id == current_user.id,
            VoiceAgent.provider == "voizematic",
        )
    )

    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Voizematic voice agent not found",
        )

    if not agent.provider_agent_id:
        raise HTTPException(
            status_code=400,
            detail="Voice agent does not have a Voizematic agent ID",
        )

    service = VoizematicPhoneNumberService()

    try:
        # Assign number through Voizematic
        provider_response = await service.assign_number_to_agent(
            number_id=number.provider_number_id,
            agent_id=agent.provider_agent_id,
        )

        # Update our local database only after provider success
        agent.voice_number_id = number.id

        await db.commit()

        return {
            "success": True,
            "message": "Phone number assigned to voice agent successfully",
            "data": {
                "voice_number_id": number.id,
                "phone_number": number.phone_number,
                "voice_agent_id": agent.id,
                "provider_agent_id": agent.provider_agent_id,
                "provider": "voizematic",
                "provider_response": provider_response,
            },
        }

    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
