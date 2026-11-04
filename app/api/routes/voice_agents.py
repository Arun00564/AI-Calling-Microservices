from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.db.models.voice_agent import VoiceAgent
from app.db.models.voice_number import VoiceNumber

from app.api.dependencies import get_current_user
from app.services.voice_call import VoiceCallService
from app.services.voizematic import (
    VoizematicAgentService,
    VoizematicPhoneNumberService,
)

from app.schemas.voice_agent import (
    ToggleWhatsAppRequest,
    VoiceCallExcelDataRequest,
    AssignVoiceNumberRequest,
    VoizematicAgentUpdateRequest,
)
from app.schemas.voizematic_agent import VoizematicAgentCreateRequest

router = APIRouter(
    prefix="/api/v1/voice-agents",
    tags=["Voice Agents"],
)


@router.get("/")
async def get_voice_agents(
    voice_number: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_voice_agents(voice_number_id=voice_number)

    return {
        "status": 200,
        "message": "The response contains the requested voice agents.",
        "success": True,
        "data": result,
    }


@router.get("/{agent_id}")
async def get_voice_agent_details(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_voice_agent_details(agent_id=agent_id)

    return {
        "status": 200,
        "message": "Voice agent details retrieved successfully.",
        "success": True,
        "data": result,
    }


@router.post("/{agent_id}/toggle-whatsapp/")
async def toggle_whatsapp(
    agent_id: int,
    request: ToggleWhatsAppRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    result = await service.toggle_whatsapp(
        agent_id=agent_id,
        enabled=request.enabled,
    )

    return {
        "status": 200,
        "message": (
            f"WhatsApp sending is now "
            f"{'ON' if result['send_whatsapp_after_call_trigger'] else 'OFF'}"
        ),
        "success": True,
        "data": result,
    }


@router.post("/{agent_id}/voice-call-excel-data/")
async def get_data_based_on_excel_columns(
    agent_id: int,
    request: VoiceCallExcelDataRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = VoiceCallService(
        db=db,
        current_user=current_user,
    )

    return await service.export_voice_call_excel(
        agent_id=agent_id,
        selected_columns=request.columns,
    )


@router.post("/create/", status_code=status.HTTP_201_CREATED)
async def create_voizematic_agent(
    request: VoizematicAgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # ==========================================
    # 1. Validate Voice Number
    # ==========================================

    result = await db.execute(
        select(VoiceNumber).where(
            VoiceNumber.user_id == current_user.id,
            VoiceNumber.provider == "voizematic",
            VoiceNumber.is_active.is_(True),
        )
    )

    # voice_number = result.scalar_one_or_none()
    voice_number = result.scalars().first()

    if voice_number is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice number not found or inactive.",
        )

    if not voice_number.provider_number_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice agent provider number ID is missing.",
        )

    # ==========================================
    # 2. Prepare Provider Payload
    # ==========================================

    payload = {
        "name": request.name,
        "system_prompt": request.system_prompt,
        "type": request.type,
    }

    if request.greeting is not None:
        payload["greeting"] = request.greeting

    if request.voice is not None:
        payload["voice"] = request.voice

    # ==========================================
    # 3. Create Agent in Voizematic
    # ==========================================

    service = VoizematicAgentService()

    provider_response = await service.create_agent(
        payload=payload,
    )

    # Support direct response or data-wrapped response.
    agent_data = provider_response.get("data", provider_response)

    if isinstance(agent_data, dict) and isinstance(agent_data.get("agent"), dict):
        agent_data = agent_data["agent"]

    if not isinstance(agent_data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response received from Voice Agent provider.",
        )

    provider_agent_id = agent_data.get("id")

    if provider_agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Voice agent not found.",
                "provider_response": provider_response,
            },
        )

    # ==========================================
    # 4. Save Agent in Local Database
    # ==========================================

    agent = VoiceAgent(
        user_id=current_user.id,
        # voice_number_id=voice_number.id,
        voice_number_id=None,
        name=request.name,
        provider="voizematic",
        provider_agent_id=str(provider_agent_id),
        plivo_agent_id=None,
        type=agent_data.get("type", request.type),
        greeting=agent_data.get("greeting", request.greeting),
        system_prompt=agent_data.get(
            "system_prompt",
            request.system_prompt,
        ),
        voice=agent_data.get("voice", request.voice),
        knowledge_base_ids=agent_data.get(
            "knowledge_base_ids",
            [],
        ),
        booking_url=agent_data.get("booking_url"),
        provider_config=provider_response,
        input_schema=[],
        is_number_assigned=False,
        is_active=True,
    )

    db.add(agent)

    await db.commit()
    await db.refresh(agent)

    # ==========================================
    # 5. Assign Number to Provider Agent
    # ==========================================

    # assignment_result = None
    # assignment_error = None

    # try:
    #     phone_service = VoizematicPhoneNumberService()

    #     assignment_result = await phone_service.assign_number_to_agent(
    #         number_id=voice_number.provider_number_id,
    #         agent_id=int(provider_agent_id),
    #     )

    # except Exception as exc:
    #     assignment_error = str(exc)

    # ==========================================
    # 6. Response
    # ==========================================

    return {
        "status": 201,
        "success": True,
        "message": (
            "Voice agent created successfully."
            # if assignment_error is None
            # else "Agent created, but phone number assignment failed."
        ),
        "data": {
            "id": agent.id,
            "name": agent.name,
            "provider": agent.provider,
            "provider_agent_id": agent.provider_agent_id,
            "voice_number_id": agent.voice_number_id,
            "type": agent.type,
            "greeting": agent.greeting,
            "system_prompt": agent.system_prompt,
            "voice": agent.voice,
            "knowledge_base_ids": agent.knowledge_base_ids,
            "booking_url": agent.booking_url,
            "provider_config": agent.provider_config,
            "is_number_assigned": agent.is_number_assigned,
            # "number_assignment": {
            #     "success": assignment_error is None,
            #     "response": assignment_result,
            #     "error": assignment_error,
            # },
            "is_active": agent.is_active,
        },
    }


@router.put("/{agent_id}/")
async def update_voizematic_agent(
    agent_id: int,
    request: VoizematicAgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # ==========================================
    # 1. Get Agent
    # ==========================================

    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
            VoiceAgent.provider == "voizematic",
            VoiceAgent.is_active.is_(True),
        )
    )

    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice agent not found.",
        )

    if not agent.provider_agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider agent ID is missing.",
        )

    # ==========================================
    # 2. Prepare Update Payload
    # ==========================================

    payload = request.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least one field to update.",
        )

    # ==========================================
    # 3. Update Agent in Voizematic
    # ==========================================

    service = VoizematicAgentService()

    provider_response = await service.update_agent(
        agent_id=agent.provider_agent_id,
        payload=payload,
    )

    # ==========================================
    # 4. Extract Provider Response
    # ==========================================

    agent_data = provider_response.get("data", provider_response)

    if isinstance(agent_data, dict) and isinstance(agent_data.get("agent"), dict):
        agent_data = agent_data["agent"]

    if not isinstance(agent_data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response received from Voizematic.",
        )

    # ==========================================
    # 5. Update Local Database
    # ==========================================

    update_fields = [
        "name",
        "system_prompt",
        "greeting",
        "voice",
        "booking_url",
    ]

    for field in update_fields:
        if field in payload:
            setattr(
                agent,
                field,
                agent_data.get(field, payload[field]),
            )

        elif field in agent_data:
            setattr(agent, field, agent_data[field])

    agent.provider_config = provider_response

    await db.commit()
    await db.refresh(agent)

    # ==========================================
    # 6. Response
    # ==========================================

    return {
        "status": 200,
        "success": True,
        "message": "Voice agent updated successfully.",
        "data": {
            "id": agent.id,
            "name": agent.name,
            "provider": agent.provider,
            "provider_agent_id": agent.provider_agent_id,
            "voice_number_id": agent.voice_number_id,
            "type": agent.type,
            "greeting": agent.greeting,
            "system_prompt": agent.system_prompt,
            "voice": agent.voice,
            "knowledge_base_ids": agent.knowledge_base_ids,
            "booking_url": agent.booking_url,
            "provider_config": agent.provider_config,
            "is_number_assigned": agent.is_number_assigned,
            "is_active": agent.is_active,
        },
    }


@router.delete("/{agent_id}/")
async def delete_voizematic_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # ==========================================
    # 1. Get Agent
    # ==========================================

    # 1. Get agent
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
            VoiceAgent.provider == "voizematic",
            VoiceAgent.is_active.is_(True),
        )
    )

    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice agent not found.",
        )

    # 2. Unassign phone number if assigned
    if agent.is_number_assigned and agent.voice_number_id:

        result = await db.execute(
            select(VoiceNumber).where(
                VoiceNumber.id == agent.voice_number_id,
                VoiceNumber.user_id == current_user.id,
            )
        )

        voice_number = result.scalar_one_or_none()

        if voice_number and voice_number.provider_number_id:
            phone_service = VoizematicPhoneNumberService()

            await phone_service.unassign_number_from_agent(
                number_id=voice_number.provider_number_id,
                agent_id=int(agent.provider_agent_id),
            )

    # 3. Soft delete
    agent.is_active = False
    agent.is_number_assigned = False
    agent.voice_number_id = None

    await db.commit()
    await db.refresh(agent)

    # 4. Response
    return {
        "status": 200,
        "success": True,
        "message": "Voice agent deactivated successfully.",
        "data": None,
    }


@router.post("/{agent_id}/assign-number/")
async def assign_voice_number(
    agent_id: int,
    payload: AssignVoiceNumberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # Get agent
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
            VoiceAgent.is_active.is_(True),
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found.")

    if agent.provider != "voizematic":
        raise HTTPException(
            status_code=400,
            detail="This API is currently for Voizematic agents only.",
        )

    # Get phone number
    result = await db.execute(
        select(VoiceNumber).where(
            VoiceNumber.id == payload.voice_number_id,
            VoiceNumber.user_id == current_user.id,
            VoiceNumber.is_active.is_(True),
        )
    )
    voice_number = result.scalar_one_or_none()

    if not voice_number:
        raise HTTPException(status_code=404, detail="Phone number not found.")

    if voice_number.provider != "voizematic":
        raise HTTPException(
            status_code=400,
            detail="Please select a Voizematic phone number.",
        )

    if not voice_number.provider_number_id:
        raise HTTPException(
            status_code=400,
            detail="Provider phone number ID is missing.",
        )

    if not agent.provider_agent_id:
        raise HTTPException(
            status_code=400,
            detail="Provider agent ID is missing.",
        )

    # Prevent assigning an agent that already has another number
    if agent.is_number_assigned and agent.voice_number_id:
        if agent.voice_number_id == voice_number.id:
            return {
                "success": True,
                "message": "This number is already assigned to this agent.",
            }

        raise HTTPException(
            status_code=409,
            detail="This agent already has a phone number assigned. Unassign it first.",
        )

    service = VoizematicPhoneNumberService()

    # Check existing assignments on Voizematic
    existing_agents = await service.get_assigned_agents(voice_number.provider_number_id)

    same_type_agents = [
        item for item in existing_agents if item.get("type") == agent.type
    ]

    if same_type_agents:
        existing_agent = same_type_agents[0]

        raise HTTPException(
            status_code=409,
            detail=(
                f"This number is already assigned to "
                f"{existing_agent.get('name')}. Please unassign it first."
            ),
        )

    # Assign through Voizematic
    await service.assign_number_to_agent(
        number_id=voice_number.provider_number_id,
        agent_id=int(agent.provider_agent_id),
    )

    # Update local DB
    agent.voice_number_id = voice_number.id
    agent.is_number_assigned = True

    await db.commit()
    await db.refresh(agent)

    return {
        "success": True,
        "message": "Phone number assigned successfully.",
        "data": {
            "agent_id": agent.id,
            "provider_agent_id": agent.provider_agent_id,
            "voice_number_id": voice_number.id,
            "phone_number": voice_number.phone_number,
            "is_number_assigned": agent.is_number_assigned,
        },
    }


@router.delete("/{agent_id}/unassign-number/")
async def unassign_voice_number(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    # Get agent
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
            VoiceAgent.is_active.is_(True),
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found.")

    if agent.provider != "voizematic":
        raise HTTPException(
            status_code=400,
            detail="This API is currently for Voizematic agents only.",
        )

    if not agent.is_number_assigned or not agent.voice_number_id:
        return {
            "success": True,
            "message": "No phone number is currently assigned to this agent.",
        }

    # Get assigned number
    result = await db.execute(
        select(VoiceNumber).where(
            VoiceNumber.id == agent.voice_number_id,
            VoiceNumber.user_id == current_user.id,
        )
    )
    voice_number = result.scalar_one_or_none()

    if not voice_number or not voice_number.provider_number_id:
        raise HTTPException(
            status_code=404,
            detail="Assigned phone number not found.",
        )

    if not agent.provider_agent_id:
        raise HTTPException(
            status_code=400,
            detail="Provider agent ID is missing.",
        )

    service = VoizematicPhoneNumberService()

    # Unassign through Voizematic
    await service.unassign_number_from_agent(
        number_id=voice_number.provider_number_id,
        agent_id=int(agent.provider_agent_id),
    )

    # Update local DB
    agent.voice_number_id = None
    agent.is_number_assigned = False

    await db.commit()
    await db.refresh(agent)

    return {
        "success": True,
        "message": "Phone number unassigned successfully.",
        "data": {
            "agent_id": agent.id,
            "voice_number_id": None,
            "is_number_assigned": False,
        },
    }
