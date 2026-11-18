import json
import phonenumbers
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

from fastapi.responses import StreamingResponse

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_details import UserDetails
from app.db.models.voice_agent import VoiceAgent
from app.db.models.customer import Customer
from app.db.models.voice_call_logs import VoiceCallLog
from app.db.models.voice_agent_field import VoiceAgentField

from app.db.models.voice_number import VoiceNumber
from app.services.plivo import PlivoVoiceService
from app.tasks.voice_tasks import initiate_bulk_voice_call
from app.constants.voice_calls import BASE_COLUMNS, BASE_COLUMN_MAPPING
from app.utils.voice_call import normalize_hangup_data

import pandas as pd


class VoiceCallService:

    def __init__(
        self,
        db: AsyncSession,
        current_user: UserDetails,
    ):
        self.db = db
        self.current_user = current_user

    def format_transcription(self, transcription_text):
        """
        Convert stored Plivo transcription into
        frontend-friendly conversation format.

        Example input:
            [Ai_agent] Hello
            [Customer] Hi

        Example output:
            [
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Hi"}
            ]
        """

        if not transcription_text:
            return []

        formatted = []

        lines = transcription_text.split("\n")

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Customer
            if line.startswith("[Customer]"):
                content = line.replace(
                    "[Customer]",
                    "",
                ).strip()

                formatted.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )

            # AI Agent
            elif line.startswith("[Ai_agent]"):
                content = line.replace(
                    "[Ai_agent]",
                    "",
                ).strip()

                formatted.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )

        return formatted

    def get_value_by_suffix(
        self,
        data: dict,
        suffix: str,
    ):
        """
        Find a value from a dictionary where the key
        ends with the given suffix.

        Example:
            "Dial Lead.call_status": "completed"

        get_value_by_suffix(data, "call_status")
        -> "completed"
        """

        if not data:
            return ""

        for key, value in data.items():
            if str(key).endswith(suffix):
                return value

        return ""

    async def get_agent(
        self,
        agent_id: int,
    ) -> VoiceAgent:

        result = await self.db.execute(
            select(VoiceAgent).where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
        )

        agent = result.scalar_one_or_none()

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found or inactive.",
            )

        return agent

    def validate_call_data(
        self,
        agent: VoiceAgent,
        call_data: dict[str, Any],
    ) -> None:

        schema = agent.input_schema or []

        errors = {}

        for field in schema:

            key = field.get("key")

            if not key:
                continue

            label = field.get("label", key)
            required = field.get("required", False)

            value = call_data.get(key)

            if required and not value:
                errors[key] = f"{label} is required"

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Validation failed.",
                    "errors": errors,
                },
            )

    # def normalize_phone_number(
    #     self,
    #     call_data: dict[str, Any],
    # ) -> str:

    #     country_code = str(call_data.get("country_code", "")).strip()

    #     phone_number = str(call_data.get("phone_number", "")).strip()

    #     country_code = "".join(filter(str.isdigit, country_code))

    #     phone_number = "".join(filter(str.isdigit, phone_number))

    #     if not country_code:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="Country code is required.",
    #         )

    #     if not phone_number:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="Phone number is required.",
    #         )

    #     # Remove country code if already present
    #     if phone_number.startswith(country_code):
    #         phone_number = phone_number[len(country_code) :]

    #     full_phone_number = f"+{country_code}{phone_number}"

    #     return full_phone_number

    def normalize_phone_number(
        self,
        call_data: dict[str, Any],
    ) -> str:

        country_code = str(call_data.get("country_code", "")).strip()

        phone_number = str(call_data.get("phone_number", "")).strip()

        country_code = "".join(filter(str.isdigit, country_code))
        phone_number = "".join(filter(str.isdigit, phone_number))

        if not country_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Country code is required.",
            )

        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is required.",
            )

        # Remove country code only when the number is longer
        # than a local number and already contains the country code.
        if phone_number.startswith(country_code):
            if len(phone_number) > 10:
                phone_number = phone_number[len(country_code) :]

        full_phone_number = f"+{country_code}{phone_number}"

        return full_phone_number

    async def get_or_create_customer(
        self,
        call_data: dict[str, Any],
        full_phone_number: str,
    ) -> Customer:

        # lead_name = call_data.get(
        #     "lead_name",
        #     "",
        # )

        # lead_name = call_data.get("customer_name") or call_data.get("full_name") or ""
        lead_name = (
            call_data.get("lead_name")
            or call_data.get("customer_name")
            or call_data.get("full_name")
            or ""
        )

        email = call_data.get("email")

        country_code = call_data.get("country_code")

        result = await self.db.execute(
            select(Customer).where(
                Customer.mobile_number == full_phone_number,
                Customer.user_id == self.current_user.id,
            )
        )

        customer = result.scalar_one_or_none()

        if customer is None:

            # customer = Customer(
            #     user_id=self.current_user.id,
            #     full_name=lead_name,
            #     email=email,
            #     mobile_number=full_phone_number,
            #     status="ACTIVE",
            # )

            customer = Customer(
                user_id=self.current_user.id,
                full_name=lead_name,
                email=email,
                country_code=country_code,
                mobile_number=full_phone_number,
                status="ACTIVE",
            )

            self.db.add(customer)

            await self.db.flush()

        else:

            if lead_name:
                customer.full_name = lead_name

            if email:
                customer.email = email

            customer.status = "ACTIVE"

            await self.db.flush()

        return customer

    async def get_previous_call_data(
        self,
        customer_id: int,
    ) -> dict[str, Any]:

        result = await self.db.execute(
            select(VoiceCallLog)
            .where(
                VoiceCallLog.customer_id == customer_id,
                VoiceCallLog.user_id == self.current_user.id,
            )
            .order_by(VoiceCallLog.created_at.desc())
            .limit(1)
        )

        latest_call = result.scalar_one_or_none()

        if latest_call is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Previous call details not found.",
            )

        return latest_call.call_variables or {}

    async def start_call(
        self,
        agent_id: int,
        customer_id: int | None,
        call_data: dict[str, Any],
        organisation_id: str | None = None,
        product_id: str | None = None,
        feature_id: str | None = None,
        knowledge_base_id: int | None = None,
        context: str | None = None,
        campaign_id: int | None = None,
        customer_list_id: int | None = None,
        use_previous_call_data: bool = False,
    ) -> dict[str, Any]:

        # if not organisation_id:
        #     return {
        #         "success": False,
        #         "status": 400,
        #         "message": "organisation_id is required.",
        #     }

        # if not product_id:
        #     return {
        #         "success": False,
        #         "status": 400,
        #         "message": "product_id is required.",
        #     }

        # if not feature_id:
        #     return {
        #         "success": False,
        #         "status": 400,
        #         "message": "feature_id is required.",
        #     }

        # -----------------------------------------
        # 1. Get Agent
        # -----------------------------------------

        agent = await self.get_agent(agent_id)
        provider = (agent.provider or "plivo").lower()

        # -----------------------------------------
        # 2. Previous Call Data
        # -----------------------------------------

        if customer_id and use_previous_call_data:
            call_data = await self.get_previous_call_data(customer_id)

        # -----------------------------------------
        # 3. Validate Call Data
        # -----------------------------------------

        self.validate_call_data(
            agent,
            call_data,
        )

        # -----------------------------------------
        # 4. Normalize Phone
        # -----------------------------------------

        # full_phone_number = self.normalize_phone_number(call_data)
        # call_data["phone_number"] = full_phone_number

        # 4. Normalize Phone

        if provider := (agent.provider or "plivo").lower():
            if provider == "voizematic":
                phone_number = str(call_data.get("phone_number", "")).strip()

                # If the number already contains country code, extract it.
                if phone_number.startswith("+"):
                    digits = "".join(filter(str.isdigit, phone_number))

                    # Extract country code using phonenumbers library.

                    try:
                        parsed_number = phonenumbers.parse(phone_number, None)

                        call_data["country_code"] = str(parsed_number.country_code)
                        call_data["phone_number"] = str(parsed_number.national_number)

                    except phonenumbers.NumberParseException:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid international phone number.",
                        )

        full_phone_number = self.normalize_phone_number(call_data)

        call_data["phone_number"] = full_phone_number

        # -----------------------------------------
        # 5. Customer
        # -----------------------------------------

        # customer = await self.get_or_create_customer(
        #     call_data,
        #     full_phone_number,
        # )

        if customer_id is not None:
            # Campaign / existing customer call:
            # Always use the existing customer record.
            result = await self.db.execute(
                select(Customer).where(
                    Customer.id == customer_id,
                    Customer.user_id == self.current_user.id,
                    Customer.deleted_at.is_(None),
                )
            )

            customer = result.scalar_one_or_none()

            if customer is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found.",
                )

        else:
            # Quick call without an existing customer:
            # Create or retrieve customer.
            customer = await self.get_or_create_customer(
                call_data,
                full_phone_number,
            )

        # # -----------------------------------------
        # # 6. Trigger Plivo
        # # -----------------------------------------

        # if not agent.plivo_agent_id:

        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail="Plivo agent ID is not configured.",
        #     )

        # plivo_service = PlivoVoiceService(flow_id=agent.plivo_agent_id)

        # plivo_response = await plivo_service.trigger_flow_call(variables=call_data)

        # if not plivo_response.get("success"):

        #     raise HTTPException(
        #         status_code=status.HTTP_502_BAD_GATEWAY,
        #         detail={
        #             "message": "Plivo call failed.",
        #             "error": plivo_response.get("error"),
        #         },
        #     )

        # # -----------------------------------------
        # # 7. Extract Plivo IDs
        # # -----------------------------------------

        # response_json = plivo_response.get("response_json") or {}

        # api_id = response_json.get("api_id")

        # phlo_id = response_json.get("phlo_id")

        # # -----------------------------------------
        # # 8. Create Call Log
        # # -----------------------------------------

        # call_log = VoiceCallLog(
        #     flow_run_uuid=api_id,
        #     flow_uuid=phlo_id,
        #     voice_agent_id=agent.id,
        #     customer_id=customer.id,
        #     user_id=self.current_user.id,
        #     from_number_id=agent.voice_number_id,
        #     organisation_id=organisation_id,
        #     product_id=product_id,
        #     feature_id=feature_id,
        #     to_number=full_phone_number,
        #     call_status="initiated",
        #     call_variables=call_data,
        # )

        # self.db.add(call_log)

        # await self.db.commit()

        # await self.db.refresh(call_log)

        # -----------------------------------------
        # 6. Trigger Call Through Selected Provider
        # -----------------------------------------

        # provider = (agent.provider or "plivo").lower()

        provider_call_id = None
        api_id = None
        phlo_id = None

        if provider == "plivo":

            if not agent.plivo_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plivo agent ID is not configured.",
                )

            plivo_service = PlivoVoiceService(flow_id=agent.plivo_agent_id)

            provider_response = await plivo_service.trigger_flow_call(
                variables=call_data
            )

            if not provider_response.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "message": "Plivo call failed.",
                        "error": provider_response.get("error"),
                    },
                )

            response_json = provider_response.get("response_json") or {}

            api_id = response_json.get("api_id")
            phlo_id = response_json.get("phlo_id")

        elif provider == "voizematic":

            from app.services.voizematic import VoizematicVoiceService

            if not agent.provider_agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Voizematic agent ID is not configured.",
                )

            voizematic_service = VoizematicVoiceService()

            # -----------------------------------------
            # 1. Prepare Context
            # -----------------------------------------

            # Use frontend-provided context if available.
            # Otherwise, generate context from call_data.
            call_context = context

            if call_context is None:
                call_context = json.dumps(
                    call_data,
                    ensure_ascii=False,
                    default=str,
                )

            # -----------------------------------------
            # 2. Prepare Knowledge Base
            # -----------------------------------------

            # Use frontend-selected knowledge base first.
            # Otherwise, use the agent's configured knowledge base.
            selected_knowledge_base_id = knowledge_base_id

            if selected_knowledge_base_id is None and agent.knowledge_base_ids:
                selected_knowledge_base_id = agent.knowledge_base_ids[0]

            # -----------------------------------------
            # 3. Trigger Voizematic Call
            # -----------------------------------------

            voizematic_response = await voizematic_service.trigger_call(
                agent_id=int(agent.provider_agent_id),
                to_number=full_phone_number,
                context=call_context,
                knowledge_base_id=selected_knowledge_base_id,
            )

            if not voizematic_response.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to initiate call.",
                )

            # -----------------------------------------
            # 4. Extract Provider Call ID
            # -----------------------------------------

            response_json = voizematic_response.get("response_json") or {}

            # provider_call_id = voizematic_response.get("call_id") or response_json.get(
            #     "call_id"
            # )

            # if provider_call_id is None:
            #     raise HTTPException(
            #         status_code=status.HTTP_502_BAD_GATEWAY,
            #         detail={
            #             "message": "Voizematic did not return a call ID.",
            #             "provider_response": response_json,
            #         },
            #     )

            # provider_data = response_json.get("data") or {}
            provider_call_id = voizematic_response.get("call_id")
            api_id = voizematic_response.get("job_id")

            # provider_call_id = (
            #     provider_data.get("call_id")
            #     or response_json.get("call_id")
            #     or voizematic_response.get("call_id")
            # )

            if provider_call_id is None:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "message": "Service did not return a call ID.",
                        "provider_response": response_json,
                    },
                )

            provider_call_id = str(provider_call_id)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported voice provider: {provider}",
            )

        # -----------------------------------------
        # 7. Create Call Log
        # -----------------------------------------

        call_log = VoiceCallLog(
            provider=provider,
            provider_call_id=(
                str(provider_call_id) if provider_call_id is not None else None
            ),
            flow_run_uuid=api_id,
            flow_uuid=phlo_id,
            voice_agent_id=agent.id,
            customer_id=customer.id,
            user_id=self.current_user.id,
            from_number_id=agent.voice_number_id,
            organisation_id=organisation_id,
            product_id=product_id,
            feature_id=feature_id,
            to_number=full_phone_number,
            call_status=("queued" if provider == "voizematic" else "initiated"),
            call_variables=call_data,
            raw_event_data=(response_json if provider == "voizematic" else None),
            campaign_id=campaign_id,
            customer_list_id=customer_list_id,
        )

        self.db.add(call_log)

        await self.db.commit()
        await self.db.refresh(call_log)

        # -----------------------------------------
        # 8. Return
        # -----------------------------------------

        response_data = {
            "call_log_id": call_log.id,
            "provider": provider,
            "provider_call_id": call_log.provider_call_id,
            "flow_run_uuid": api_id,
            "call_status": call_log.call_status,
            "organisation_id": organisation_id,
            "product_id": product_id,
            "feature_id": feature_id,
            "agent_id": agent_id,
        }

        response_data.update(call_data)

        return response_data

        # -----------------------------------------
        # 9. Return
        # -----------------------------------------

        # response_data = {
        #     "call_log_id": call_log.id,
        #     "flow_run_uuid": api_id,
        #     "call_status": "initiated",
        #     "organisation_id": organisation_id,
        #     "product_id": product_id,
        #     "feature_id": feature_id,
        #     "agent_id": agent_id,
        # }

        # # Add dynamic lead/customer fields
        # response_data.update(call_data)

        # return response_data

        # return {
        #     "flow_run_uuid": api_id,
        #     "call_data": call_data,
        #     "call_log_id": call_log.id,
        #     "organisation_id": organisation_id,
        #     "product_id": product_id,
        #     "feature_id": feature_id,
        #     "agent_id": agent_id,
        #     "call_status": "initiated",
        # }

    async def get_call_details(
        self,
        flow_run_uuid: UUID,
    ):
        result = await self.db.execute(
            select(VoiceCallLog)
            .options(
                selectinload(VoiceCallLog.customer),
                selectinload(VoiceCallLog.voice_agent),
            )
            .where(VoiceCallLog.flow_run_uuid == flow_run_uuid)
        )

        call = result.scalar_one_or_none()

        lead_data = call.call_variables or {}

        if not call:
            return None

        # Security check
        if call.user_id != self.current_user.id:
            raise PermissionError("Unauthorized access")

        hangup_data = call.hangup_data or {}
        recording_data = call.recording_data or {}

        return {
            "lead": lead_data,
            "call_status": self.get_value_by_suffix(
                hangup_data,
                "call_status",
            ),
            "from_country": self.get_value_by_suffix(
                hangup_data,
                "from_country",
            ),
            "conversation_id": self.get_value_by_suffix(
                hangup_data,
                "conversation_id",
            ),
            "duration": hangup_data.get("call_duration", ""),
            "call_end_reason": hangup_data.get("hangup_source", ""),
            "summary": recording_data.get("conversation_summary", ""),
            "transcription": self.format_transcription(
                recording_data.get(
                    "transcription",
                    "",
                )
            ),
            "recording_link": recording_data.get("recording_url", ""),
            "recording_start_time": recording_data.get("recording_start_time", ""),
            "recording_end_time": recording_data.get("recording_end_time", ""),
            "created_at": (
                call.created_at.astimezone(ZoneInfo("Asia/Kolkata")).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if call.created_at
                else ""
            ),
            "organisation_id": call.organisation_id,
            "product_id": call.product_id,
            "feature_id": call.feature_id,
            "voice_agent_id": call.voice_agent_id,
        }

    async def manual_bulk_calls(
        self,
        agent_id: int,
        leads: list[dict],
        organisation_id: str,
        product_id: str,
        feature_id: str,
    ):

        scheduled_calls = []
        validation_errors = []

        schema = agent_id.input_schema or []

        for index, lead in enumerate(leads):

            call_data = lead

            if not isinstance(call_data, dict):
                validation_errors.append(
                    {
                        "lead_index": index,
                        "error": "Lead data must be an object.",
                    }
                )
                continue

            errors = {}

            for field in schema:

                key = field.get("key")
                label = field.get("label", key)
                required = field.get("required", False)

                value = call_data.get(key)

                if required and not value:
                    errors[key] = f"{label} is required"

            if errors:
                validation_errors.append(
                    {
                        "lead_index": index,
                        "errors": errors,
                    }
                )
                continue

            # Normalize phone
            country_code = str(call_data.get("country_code", "")).strip()

            phone_number = str(call_data.get("phone_number", "")).strip()

            country_code = "".join(filter(str.isdigit, country_code))

            phone_number = "".join(filter(str.isdigit, phone_number))

            if phone_number.startswith(country_code):
                phone_number = phone_number[len(country_code) :]

            call_data["phone_number"] = f"+{country_code}{phone_number}"

            # ==========================================
            # Queue Celery task
            # ==========================================

            task = initiate_bulk_voice_call.delay(
                self.current_user.id,
                agent_id,
                call_data,
                organisation_id,
                product_id,
                feature_id,
            )

            scheduled_calls.append(
                {
                    "lead_index": index,
                    "task_id": task.id,
                    "status": "scheduled",
                    "call_data": call_data,
                }
            )

    # async def get_voice_agents(
    #     self,
    #     voice_number_id: int | None = None,
    # ):

    #     # ==========================================
    #     # Validate voice number if filter is provided
    #     # ==========================================
    #     if voice_number_id is not None:
    #         voice_number_result = await self.db.execute(
    #             select(VoiceNumber).where(
    #                 VoiceNumber.id == voice_number_id,
    #                 VoiceNumber.user_id == self.current_user.id,
    #                 VoiceNumber.is_active.is_(True),
    #             )
    #         )

    #         voice_number = voice_number_result.scalar_one_or_none()

    #         if voice_number is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail=f"Voice number with ID {voice_number_id} not found or inactive.",
    #                 # detail={
    #                 #     "message": f"Voice number with ID {voice_number_id} not found or inactive.",
    #                 # },
    #             )

    #     # ==========================================
    #     # Fetch voice agents
    #     # ==========================================
    #     query = (
    #         select(VoiceAgent)
    #         .options(joinedload(VoiceAgent.voice_numbers))
    #         .where(
    #             VoiceAgent.user_id == self.current_user.id,
    #             VoiceAgent.is_active.is_(True),
    #         )
    #         .order_by(VoiceAgent.created_at.desc())
    #     )

    #     if voice_number_id:
    #         query = query.where(VoiceAgent.voice_number_id == voice_number_id)

    #     result = await self.db.execute(query)

    #     agents = result.scalars().unique().all()

    #     return [
    #         {
    #             "id": agent.id,
    #             "name": agent.name,
    #             "plivo_agent_id": agent.plivo_agent_id,
    #             "voice_number": {
    #                 "id": agent.voice_numbers.id if agent.voice_numbers else None,
    #                 "calling_number": (
    #                     agent.voice_numbers.phone_number
    #                     if agent.voice_numbers
    #                     else None
    #                 ),
    #             },
    #             "input_schema": agent.input_schema or [],
    #             "is_active": agent.is_active,
    #             "send_whatsapp_after_call_trigger": (
    #                 agent.send_whatsapp_after_call_trigger
    #             ),
    #             "created_at": (
    #                 agent.created_at.strftime("%Y-%m-%d %H:%M:%S")
    #                 if agent.created_at
    #                 else ""
    #             ),
    #         }
    #         for agent in agents
    #     ]

    # updated voice agent methods with voizematics with include is_number_assigned field and handle cases where voice_number_id can be None
    async def get_voice_agents(
        self,
        voice_number_id: int | None = None,
    ):
        # ==========================================
        # 1. Validate voice number if filter provided
        # ==========================================
        if voice_number_id is not None:
            voice_number_result = await self.db.execute(
                select(VoiceNumber).where(
                    VoiceNumber.id == voice_number_id,
                    VoiceNumber.user_id == self.current_user.id,
                    VoiceNumber.is_active.is_(True),
                )
            )

            voice_number = voice_number_result.scalar_one_or_none()

            if voice_number is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Voice number with ID {voice_number_id} "
                        "not found or inactive."
                    ),
                )

        # ==========================================
        # 2. Fetch voice agents
        # ==========================================
        query = (
            select(VoiceAgent)
            .options(joinedload(VoiceAgent.voice_numbers))
            .where(
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
            .order_by(VoiceAgent.created_at.desc())
        )

        if voice_number_id is not None:
            query = query.where(VoiceAgent.voice_number_id == voice_number_id)

        result = await self.db.execute(query)

        agents = result.scalars().unique().all()

        # ==========================================
        # 3. Prepare Response
        # ==========================================
        return [
            {
                "id": agent.id,
                "name": agent.name,
                # Provider details
                "provider": agent.provider,
                "provider_agent_id": agent.provider_agent_id,
                "plivo_agent_id": agent.plivo_agent_id,
                # Phone number details
                "voice_number_id": agent.voice_number_id,
                "is_number_assigned": agent.is_number_assigned,
                "voice_number": (
                    {
                        "id": agent.voice_numbers.id,
                        "calling_number": agent.voice_numbers.phone_number,
                    }
                    if agent.voice_numbers
                    else None
                ),
                # Agent configuration
                "type": agent.type,
                "voice": agent.voice,
                "input_schema": agent.input_schema or [],
                "is_active": agent.is_active,
                "send_whatsapp_after_call_trigger": (
                    agent.send_whatsapp_after_call_trigger
                ),
                "created_at": (
                    agent.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if agent.created_at
                    else ""
                ),
            }
            for agent in agents
        ]

    # async def get_voice_agent_details(
    #     self,
    #     agent_id: int,
    # ):
    #     result = await self.db.execute(
    #         select(VoiceAgent)
    #         .options(joinedload(VoiceAgent.voice_numbers))
    #         .where(
    #             VoiceAgent.id == agent_id,
    #             VoiceAgent.user_id == self.current_user.id,
    #         )
    #     )

    #     agent = result.scalars().first()

    #     if agent is None:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail="Voice agent not found.",
    #         )

    #     return {
    #         "id": agent.id,
    #         "name": agent.name,
    #         "plivo_agent_id": agent.plivo_agent_id,
    #         "voice_number": {
    #             "id": (agent.voice_numbers.id if agent.voice_numbers else None),
    #             "phone_number": (
    #                 agent.voice_numbers.phone_number if agent.voice_numbers else None
    #             ),
    #         },
    #         "input_schema": agent.input_schema or [],
    #         "is_active": agent.is_active,
    #         "send_whatsapp_after_call_trigger": (
    #             agent.send_whatsapp_after_call_trigger
    #         ),
    #         "created_at": (
    #             agent.created_at.strftime("%Y-%m-%d %H:%M:%S")
    #             if agent.created_at
    #             else ""
    #         ),
    #         "updated_at": (
    #             agent.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    #             if agent.updated_at
    #             else ""
    #         ),
    #     }

    # update voice agent details with voizematics method to include provider details, is_number_assigned field, and handle cases where voice_number_id can be None
    async def get_voice_agent_details(
        self,
        agent_id: int,
    ):
        # ==========================================
        # 1. Fetch Voice Agent
        # ==========================================
        result = await self.db.execute(
            select(VoiceAgent)
            .options(joinedload(VoiceAgent.voice_numbers))
            .where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
            )
        )

        agent = result.scalars().first()

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found.",
            )

        # ==========================================
        # 2. Prepare Response
        # ==========================================
        return {
            "id": agent.id,
            "name": agent.name,
            # Provider details
            "provider": agent.provider,
            "provider_agent_id": agent.provider_agent_id,
            "plivo_agent_id": agent.plivo_agent_id,
            # Phone number details
            "voice_number_id": agent.voice_number_id,
            "is_number_assigned": agent.is_number_assigned,
            "voice_number": (
                {
                    "id": agent.voice_numbers.id,
                    "phone_number": agent.voice_numbers.phone_number,
                }
                if agent.voice_numbers
                else None
            ),
            # Agent configuration
            "type": agent.type,
            "greeting": agent.greeting,
            "system_prompt": agent.system_prompt,
            "voice": agent.voice,
            "knowledge_base_ids": agent.knowledge_base_ids or [],
            "booking_url": agent.booking_url,
            "input_schema": agent.input_schema or [],
            "is_active": agent.is_active,
            "send_whatsapp_after_call_trigger": (
                agent.send_whatsapp_after_call_trigger
            ),
            "created_at": (
                agent.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if agent.created_at
                else ""
            ),
            "updated_at": (
                agent.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if agent.updated_at
                else ""
            ),
        }

    async def toggle_whatsapp(
        self,
        agent_id: int,
        enabled: bool,
    ):
        result = await self.db.execute(
            select(VoiceAgent).where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
            )
        )

        agent = result.scalar_one_or_none()

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found.",
            )

        agent.send_whatsapp_after_call_trigger = enabled

        await self.db.commit()
        await self.db.refresh(agent)

        return {
            "agent_id": agent.id,
            "send_whatsapp_after_call_trigger": (
                agent.send_whatsapp_after_call_trigger
            ),
        }

    async def get_excel_columns(self):
        # Find first active agent belonging to current user
        result = await self.db.execute(
            select(VoiceAgent)
            .where(
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
            .order_by(VoiceAgent.created_at.asc())
            .limit(1)
        )

        agent = result.scalar_one_or_none()

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active voice agent found.",
            )

        # Get required dynamic fields
        result = await self.db.execute(
            select(VoiceAgentField)
            .where(
                VoiceAgentField.voice_agent_id == agent.id,
                VoiceAgentField.is_required.is_(True),
            )
            .order_by(VoiceAgentField.created_at.asc())
        )

        agent_fields = result.scalars().all()

        dynamic_columns = [
            {
                "key": field.field_key,
                "label": (
                    field.field_label or field.field_key.replace("_", " ").title()
                ),
            }
            for field in agent_fields
            if field.field_key
        ]

        columns = BASE_COLUMNS + dynamic_columns

        return columns

    async def export_voice_call_excel(
        self,
        agent_id: int,
        selected_columns: list[str],
    ):
        # =====================================================
        # Validate columns
        # =====================================================

        if not selected_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select at least one column.",
            )

        # =====================================================
        # Validate agent ownership
        # =====================================================

        result = await self.db.execute(
            select(VoiceAgent).where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
        )

        agent = result.scalar_one_or_none()

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found.",
            )

        # =====================================================
        # Get call logs
        # =====================================================

        result = await self.db.execute(
            select(VoiceCallLog)
            .options(joinedload(VoiceCallLog.customer))
            .where(
                VoiceCallLog.voice_agent_id == agent.id,
                VoiceCallLog.user_id == self.current_user.id,
            )
            .order_by(VoiceCallLog.created_at.desc())
        )

        call_logs = result.scalars().unique().all()

        # =====================================================
        # Get dynamic agent fields
        # =====================================================

        result = await self.db.execute(
            select(VoiceAgentField).where(VoiceAgentField.voice_agent_id == agent.id)
        )

        agent_fields = result.scalars().all()

        field_label_map = {
            field.field_key: (
                field.field_label or field.field_key.replace("_", " ").title()
            )
            for field in agent_fields
            if field.field_key
        }

        # =====================================================
        # Build column configuration
        # =====================================================

        column_config = []

        for col in selected_columns:

            # ---------------------------------------------
            # Base column
            # ---------------------------------------------

            if col in BASE_COLUMN_MAPPING:
                header = col.replace("_", " ").title()
                column_config.append(
                    {
                        "header": header,
                        "value": BASE_COLUMN_MAPPING[col],
                    }
                )

            # ---------------------------------------------
            # Dynamic column
            # ---------------------------------------------

            elif col in field_label_map:
                column_config.append(
                    {
                        "header": field_label_map[col],
                        "value": lambda obj, key=col: (
                            normalize_hangup_data(obj.hangup_data or {}).get(key, "")
                        ),
                    }
                )

            # ---------------------------------------------
            # Unknown column
            # ---------------------------------------------

            else:
                column_config.append(
                    {
                        "header": col,
                        "value": lambda obj: "",
                    }
                )

        # =====================================================
        # Create Excel
        # =====================================================

        wb = Workbook()

        ws = wb.active
        ws.title = "Voice Call Logs"

        # =====================================================
        # Headers
        # =====================================================

        headers = [column["header"] for column in column_config]
        ws.append(headers)

        for column_index in range(1, len(headers) + 1):
            ws.cell(
                row=1,
                column=column_index,
            ).font = Font(bold=True)

        ws.freeze_panes = "A2"

        # =====================================================
        # Rows
        # =====================================================

        for call_log in call_logs:
            row = []
            for column in column_config:

                try:
                    value = column["value"](call_log)
                except Exception:
                    value = ""

                row.append(value)

            ws.append(row)

        # =====================================================
        # Auto column width
        # =====================================================

        for column_cells in ws.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                try:
                    if cell.value:
                        max_length = max(
                            max_length,
                            len(str(cell.value)),
                        )
                except Exception:
                    pass

            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

        # =====================================================
        # Create file
        # =====================================================

        file_name = (
            f"voice_call_logs_" f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        # =====================================================
        # Return Excel
        # =====================================================

        return StreamingResponse(
            output,
            media_type=(
                "application/vnd.openxmlformats-officedocument" ".spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": (f'attachment; filename="{file_name}"')},
        )

    async def bulk_calling_upload_excel_and_initiate_calls(
        self,
        agent_id: int,
        excel_file: UploadFile,
    ):
        CHUNK_SIZE = 10
        CHUNK_DELAY = 20

        # =====================================================
        # Validate Agent
        # =====================================================

        result = await self.db.execute(
            select(VoiceAgent)
            .options(joinedload(VoiceAgent.voice_numbers))
            .where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
        )

        agent = result.unique().scalar_one_or_none()

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="Voice agent not found or inactive.",
            )

        # =====================================================
        # Validate Excel File
        # =====================================================

        if not excel_file:
            raise HTTPException(
                status_code=400,
                detail="Excel file required.",
            )

        # Optional but useful validation
        if not excel_file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=400,
                detail="Please upload a valid Excel file.",
            )

        # =====================================================
        # Read Excel
        # =====================================================

        try:
            file_content = await excel_file.read()

            df = pd.read_excel(BytesIO(file_content))

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to read Excel file: {str(e)}",
            )

        # =====================================================
        # Dynamic Schema
        # =====================================================

        schema = agent.input_schema or []

        required_columns = []

        for field in schema:
            if field.get("required"):
                field_key = field.get("key")

                if field_key:
                    required_columns.append(field_key)

        # =====================================================
        # Validate Required Columns
        # =====================================================

        missing_columns = []

        for column in required_columns:
            if column not in df.columns:
                missing_columns.append(column)

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Missing required columns in Excel.",
                    "missing_columns": missing_columns,
                },
            )

        # =====================================================
        # Convert Excel To Dict
        # =====================================================

        leads = df.fillna("").to_dict(orient="records")

        # =====================================================
        # Chunk Leads
        # =====================================================

        chunks = [
            leads[i : i + CHUNK_SIZE]
            for i in range(
                0,
                len(leads),
                CHUNK_SIZE,
            )
        ]

        scheduled_calls = []

        # =====================================================
        # Schedule Calls
        # =====================================================

        for chunk_index, chunk in enumerate(chunks):
            for lead in chunk:
                call_data = dict(lead)

                # =============================================
                # Normalize Phone
                # =============================================

                country_code = str(
                    call_data.get(
                        "country_code",
                        "",
                    )
                ).strip()

                phone_number = str(
                    call_data.get(
                        "phone_number",
                        "",
                    )
                ).strip()

                country_code = "".join(
                    filter(
                        str.isdigit,
                        country_code,
                    )
                )

                phone_number = "".join(
                    filter(
                        str.isdigit,
                        phone_number,
                    )
                ).split(
                    "."
                )[0]

                full_phone_number = f"+{country_code}{phone_number}"

                call_data["phone_number"] = full_phone_number

                # =============================================
                # Schedule Celery Task
                # =============================================

                task = initiate_bulk_voice_call.apply_async(
                    args=[
                        self.current_user.id,
                        agent.id,
                        call_data,
                    ],
                    countdown=(chunk_index * CHUNK_DELAY),
                )

                scheduled_calls.append(
                    {
                        "call_data": call_data,
                        "task_id": task.id,
                    }
                )

        # =====================================================
        # Response
        # =====================================================

        return {
            "total_calls": len(scheduled_calls),
            "total_chunks": len(chunks),
        }

    async def download_sample_excel(
        self,
        agent_id: int,
    ):
        # =====================================================
        # 1. Validate Agent
        # =====================================================

        result = await self.db.execute(
            select(VoiceAgent)
            .options(joinedload(VoiceAgent.voice_numbers))
            .where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == self.current_user.id,
                VoiceAgent.is_active.is_(True),
            )
        )
        print("Result:----", result)  # Debugging line to check the result of the query

        agent = result.unique().scalar_one_or_none()
        print("Agent:----", agent)  # Debugging line to check the retrieved agent

        if agent is None:
            raise HTTPException(
                status_code=404,
                detail="Voice agent not found or inactive.",
            )

        # =====================================================
        # 2. Get Dynamic Schema
        # =====================================================

        schema = agent.input_schema or []

        if not schema:
            raise HTTPException(
                status_code=400,
                detail="Input schema not configured for this agent.",
            )

        # =====================================================
        # 3. Generate Dynamic Columns
        # =====================================================

        columns = [field.get("key") for field in schema if field.get("key")]

        if not columns:
            raise HTTPException(
                status_code=400,
                detail="No valid fields found in input schema.",
            )

        # =====================================================
        # 4. Create Excel In Memory
        # =====================================================

        output = BytesIO()
        df = pd.DataFrame(columns=columns)

        with pd.ExcelWriter(
            output,
            engine="openpyxl",
        ) as writer:

            # =================================================
            # Main Sheet
            # =================================================

            df.to_excel(
                writer,
                index=False,
                sheet_name="Bulk Voice Calls",
            )

            worksheet = writer.sheets["Bulk Voice Calls"]

            # =================================================
            # Header Styling
            # =================================================

            header_font = Font(bold=True)
            header_alignment = Alignment(horizontal="center")

            for col_num, column_name in enumerate(
                columns,
                1,
            ):
                cell = worksheet.cell(
                    row=1,
                    column=col_num,
                )

                cell.font = header_font
                cell.alignment = header_alignment

                column_letter = get_column_letter(col_num)

                worksheet.column_dimensions[column_letter].width = 30

            # =================================================
            # Instructions Sheet
            # =================================================

            instruction_data = []

            for field in schema:
                instruction_data.append(
                    {
                        "Column": field.get("key", ""),
                        "Label": field.get("label", ""),
                        "Required": ("Yes" if field.get("required") else "No"),
                    }
                )

            instruction_df = pd.DataFrame(instruction_data)

            instruction_df.to_excel(
                writer,
                index=False,
                sheet_name="Instructions",
            )

            instruction_sheet = writer.sheets["Instructions"]

            for col_num, _ in enumerate(
                instruction_df.columns,
                1,
            ):
                cell = instruction_sheet.cell(
                    row=1,
                    column=col_num,
                )

                cell.font = header_font
                cell.alignment = header_alignment

                column_letter = get_column_letter(col_num)

                instruction_sheet.column_dimensions[column_letter].width = 30

        # =====================================================
        # Reset File Position
        # =====================================================

        output.seek(0)

        # =====================================================
        # Filename
        # =====================================================

        agent_name = agent.name or f"voice_agent_{agent.id}"

        # Make filename safer
        safe_agent_name = (
            str(agent_name).replace("/", "_").replace("\\", "_").replace(" ", "_")
        )

        filename = f"{safe_agent_name}_template.xlsx"

        # =====================================================
        # Return Excel File
        # =====================================================

        return StreamingResponse(
            output,
            media_type=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": (f'attachment; filename="{filename}"')},
        )
