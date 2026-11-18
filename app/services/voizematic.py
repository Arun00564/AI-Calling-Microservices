# import os
# import json
# import httpx


# class VoizematicVoiceService:
#     BASE_URL = os.getenv("VOIZEMATIC_BASE_URL")

#     def __init__(self):
#         self.api_key = os.getenv("VOIZEMATIC_API_KEY")

#         if not self.api_key:
#             raise ValueError("VOIZEMATIC_API_KEY is not configured")

#     async def trigger_call(
#         self,
#         agent_id: int,
#         to_number: str,
#         context: str | None = None,
#     ) -> dict:
#         headers = {
#             "Authorization": f"Bearer {self.api_key}",
#             "Content-Type": "application/json",
#         }

#         payload = {
#             "agent_id": agent_id,
#             "to_number": to_number,
#         }

#         if context:
#             payload["context"] = context[:2000]

#         async with httpx.AsyncClient(timeout=30.0) as client:
#             response = await client.post(
#                 f"{self.BASE_URL}/calls",
#                 headers=headers,
#                 json=payload,
#             )

#         try:
#             response_data = response.json()
#         except ValueError:
#             response_data = {"message": response.text}

#         if not response.is_success:
#             return {
#                 "success": False,
#                 "error": response_data,
#             }

#         return {
#             "success": True,
#             "response_json": response_data,
#         }


import os
import logging

from sqlalchemy import select
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.voice_call_logs import VoiceCallLog

from app.tasks.campaign_tasks import sync_campaign_call_status

logger = logging.getLogger(__name__)


class VoizematicPhoneNumberService:
    BASE_URL = settings.VOIZEMATIC_BASE_URL

    def __init__(self):
        self.api_key = settings.VOIZEMATIC_API_KEY

        if not self.api_key:
            raise RuntimeError("VOIZEMATIC_API_KEY is not configured.")

        if not self.BASE_URL:
            raise RuntimeError("VOIZEMATIC_BASE_URL is not configured.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def get_available_numbers(
        self,
        country: str,
        number_type: str | None = None,
        capabilities: str | None = None,
        area_code: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "country": country.upper(),
            "limit": limit,
        }

        if number_type:
            params["type"] = number_type

        if capabilities:
            params["capabilities"] = capabilities

        if area_code:
            params["area_code"] = area_code

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/phone-numbers/available",
                    headers=self.headers,
                    params=params,
                )

            if not response.is_success:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Failed to fetch available numbers.",
                        "provider_status": response.status_code,
                        "provider_response": response.text[:1000],
                    },
                )

            provider_data = response.json()

            if not provider_data.get("success"):
                raise HTTPException(
                    status_code=502,
                    detail="Voizematic could not fetch available numbers.",
                )

            numbers = provider_data.get("data", [])

            return {
                "country": country.upper(),
                "numbers": [
                    {
                        "phone_number": item["phone_number"],
                        "country": item["country"],
                        "number_type": item.get("number_type"),
                        "locality": item.get("locality"),
                        "region": item.get("region"),
                        "capabilities": item.get("capabilities", {}),
                        "setup_fee_usd": item.get("setup_fee_usd"),
                        "monthly_fee_usd": item.get("monthly_fee_usd"),
                        "setup_fee_inr": item.get("setup_fee_inr"),
                        "monthly_fee_inr": item.get("monthly_fee_inr"),
                    }
                    for item in numbers
                ],
            }

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    async def list_purchased_numbers(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/phone-numbers",
                    headers=self.headers,
                )

            if not response.is_success:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Failed to fetch purchased numbers.",
                        "provider_status": response.status_code,
                        "provider_response": response.text[:1000],
                    },
                )

            result = response.json()

            if not result.get("success"):
                raise HTTPException(
                    status_code=502,
                    detail="Voizematic did not confirm the purchased-number list.",
                )

            numbers = result.get("data")

            if not isinstance(numbers, list):
                raise HTTPException(
                    status_code=502,
                    detail="Unexpected purchased-number response from Voizematic.",
                )

            return numbers

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    async def get_number_details(self, number_id: str):
        url = f"{self.BASE_URL}/phone-numbers/{number_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers=self.headers,
            )

        if response.is_error:
            raise RuntimeError(
                f"Voizematic API error: {response.status_code} " f"- {response.text}"
            )

        return response.json()

    async def get_assigned_agents(self, number_id: str):
        response = await self.get_number_details(number_id)

        data = response.get("data", {})

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=502,
                detail="Invalid phone number response from Voizematic.",
            )

        return data.get("agents", []) or []

    async def unassign_number_from_agent(
        self,
        number_id: str,
        agent_id: int,
    ):
        url = f"{self.BASE_URL}/phone-numbers/{number_id}/agent"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    url,
                    headers=self.headers,
                    params={"agent_id": agent_id},
                )

            if response.is_error:
                raise HTTPException(
                    status_code=(
                        response.status_code if response.status_code < 500 else 502
                    ),
                    detail={
                        "message": "Failed to unassign phone number.",
                        "provider_response": response.text[:1000],
                    },
                )

            return response.json() if response.content else {"success": True}

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    async def assign_number_to_agent(
        self,
        number_id: str,
        agent_id: int,
    ):
        url = f"{self.BASE_URL}/phone-numbers/{number_id}/agent"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                url,
                headers=self.headers,
                json={"agent_id": agent_id},
            )

        if response.is_error:
            raise RuntimeError(
                f"Voizematic API error: {response.status_code} - {response.text}"
            )

        return response.json()


class VoizematicAgentService:

    BASE_URL = settings.VOIZEMATIC_BASE_URL

    def __init__(self):
        self.api_key = settings.VOIZEMATIC_API_KEY

        if not self.api_key:
            raise RuntimeError("VOIZEMATIC_API_KEY is not configured.")

        if not self.BASE_URL:
            raise RuntimeError("VOIZEMATIC_BASE_URL is not configured.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_agent(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/agents",
                    headers=self.headers,
                    json=payload,
                )

            if not response.is_success:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Failed to create Voice Agent.",
                        "provider_status": response.status_code,
                        "provider_response": response.text[:1000],
                    },
                )

            provider_data = response.json()

            if (
                not isinstance(provider_data, dict)
                or provider_data.get("success") is False
            ):
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Voizematic did not confirm agent creation.",
                        "provider_response": provider_data,
                    },
                )

            return provider_data

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    async def update_agent(
        self,
        agent_id: str,
        payload: dict,
    ):
        url = f"{self.BASE_URL}/agents/{agent_id}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    url,
                    headers=self.headers,
                    json=payload,
                )

            if response.is_error:
                raise HTTPException(
                    status_code=(
                        response.status_code if response.status_code < 500 else 502
                    ),
                    detail={
                        "message": "Failed to update Voice Agent.",
                        "provider_response": response.text[:1000],
                    },
                )

            return response.json() if response.content else {}

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    async def delete_agent(self, agent_id: str):
        url = f"{self.BASE_URL}/agents/{agent_id}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    url,
                    headers=self.headers,
                )

            if response.is_error:
                raise HTTPException(
                    status_code=(
                        response.status_code if response.status_code < 500 else 502
                    ),
                    detail={
                        "message": "Failed to delete Voice Agent.",
                        "provider_response": response.text[:1000],
                    },
                )

            return response.json() if response.content else {"success": True}

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )


class VoizematicWebhookService:
    BASE_URL = settings.VOIZEMATIC_BASE_URL

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self.api_key = settings.VOIZEMATIC_API_KEY

        if not self.api_key:
            raise RuntimeError("VOIZEMATIC_API_KEY is not configured.")

        if not self.BASE_URL:
            raise RuntimeError("VOIZEMATIC_BASE_URL is not configured.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def register_webhook(self, payload: dict):
        """
        Register webhook with Voizematic.
        """

        url = f"{self.BASE_URL}/webhooks"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                )

            if response.is_error:
                raise HTTPException(
                    status_code=(
                        response.status_code if response.status_code < 500 else 502
                    ),
                    detail={
                        "message": "Failed to register webhook.",
                        "provider_response": response.text[:1000],
                    },
                )

            return response.json() if response.content else {"success": True}

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )

    # -----------------------------------------
    # Webhook Event Handler
    # -----------------------------------------

    async def process_call_created(
        self,
        payload: dict,
    ) -> None:

        data = payload.get("data") or {}

        job_id = data.get("job_id")
        call_id = data.get("call_id")

        # if self.db is None:
        #     raise RuntimeError("Database session is required for webhook processing.")

        if not job_id:
            logger.error(
                "call.created webhook missing job_id: %s",
                payload,
            )
            return

        result = await self.db.execute(
            select(VoiceCallLog).where(
                VoiceCallLog.provider == "voizematic",
                VoiceCallLog.flow_run_uuid == str(job_id),
            )
        )

        call_log = result.scalar_one_or_none()

        if not call_log:
            logger.warning(
                "No VoiceCallLog found for Voizematic job_id: %s",
                job_id,
            )
            return

        call_log.provider_call_id = (
            str(call_id) if call_id is not None else call_log.provider_call_id
        )

        call_log.to_number = data.get("to_number") or call_log.to_number

        call_log.call_status = data.get("status") or call_log.call_status

        call_log.event_name = "call.created"
        call_log.raw_event_data = payload
        call_log.webhook_payload = payload

        await self.db.commit()

        logger.info(
            "Voizematic call.created saved successfully. "
            "CallLog ID: %s, Job ID: %s, Call ID: %s",
            call_log.id,
            job_id,
            call_id,
        )

    async def process_call_ended(
        self,
        payload: dict,
    ) -> None:

        data = payload.get("data") or {}

        call_id = data.get("call_id")

        if call_id is None:
            logger.error(
                "call.ended webhook missing call_id: %s",
                payload,
            )
            return

        result = await self.db.execute(
            select(VoiceCallLog).where(
                VoiceCallLog.provider == "voizematic",
                VoiceCallLog.provider_call_id == str(call_id),
            )
        )

        call_log = result.scalar_one_or_none()

        if not call_log:
            logger.warning(
                "No VoiceCallLog found for Voizematic call_id: %s",
                call_id,
            )
            return

        call_log.call_status = data.get("status") or call_log.call_status

        if data.get("duration_seconds") is not None:
            call_log.call_duration = int(data["duration_seconds"])

        call_log.to_number = data.get("to") or call_log.to_number

        call_log.hangup_data = data
        call_log.event_name = "call.ended"
        call_log.raw_event_data = payload
        call_log.webhook_payload = payload

        await self.db.commit()

        sync_campaign_call_status.delay(
            call_log_id=call_log.id,
            final_status="completed",
        )

        logger.info(
            "Voizematic call.ended saved successfully. "
            "CallLog ID: %s, Call ID: %s, Status: %s, Duration: %s",
            call_log.id,
            call_id,
            call_log.call_status,
            call_log.call_duration,
        )

    async def process_call_failed(
        self,
        payload: dict,
    ) -> None:

        data = payload.get("data") or {}

        call_id = data.get("call_id")

        if call_id is None:
            logger.error(
                "call.failed webhook missing call_id: %s",
                payload,
            )
            return

        result = await self.db.execute(
            select(VoiceCallLog).where(
                VoiceCallLog.provider == "voizematic",
                VoiceCallLog.provider_call_id == str(call_id),
            )
        )

        call_log = result.scalar_one_or_none()

        if not call_log:
            logger.warning(
                "No VoiceCallLog found for Voizematic call_id: %s",
                call_id,
            )
            return

        call_log.call_status = data.get("status") or "failed"

        if data.get("duration_seconds") is not None:
            call_log.call_duration = int(data["duration_seconds"])

        call_log.to_number = data.get("to") or call_log.to_number

        call_log.hangup_data = data
        call_log.event_name = "call.failed"
        call_log.raw_event_data = payload
        call_log.webhook_payload = payload

        await self.db.commit()

        sync_campaign_call_status.delay(
            call_log_id=call_log.id,
            final_status="failed",
        )

        logger.info(
            "Voizematic call.failed saved successfully. "
            "CallLog ID: %s, Call ID: %s, Status: %s",
            call_log.id,
            call_id,
            call_log.call_status,
        )

    async def process_call_transcribed(
        self,
        payload: dict,
    ) -> None:

        data = payload.get("data") or {}

        call_id = data.get("call_id")

        if call_id is None:
            logger.error(
                "call.transcribed webhook missing call_id: %s",
                payload,
            )
            return

        result = await self.db.execute(
            select(VoiceCallLog).where(
                VoiceCallLog.provider == "voizematic",
                VoiceCallLog.provider_call_id == str(call_id),
            )
        )

        call_log = result.scalar_one_or_none()

        if not call_log:
            logger.warning(
                "No VoiceCallLog found for Voizematic call_id: %s",
                call_id,
            )
            return

        # Save transcript
        if data.get("transcript") is not None:
            call_log.transcription = data["transcript"]

        # Save conversation summary
        if data.get("summary") is not None:
            call_log.conversation_summary = data["summary"]

        # Save recording URL
        if data.get("recording_url") is not None:
            call_log.recording_url = data["recording_url"]

        # Save duration
        if data.get("duration_seconds") is not None:
            call_log.call_duration = int(data["duration_seconds"])

        # Save complete recording event data
        call_log.recording_data = data

        # Save complete webhook information
        call_log.event_name = "call.transcribed"
        call_log.raw_event_data = payload
        call_log.webhook_payload = payload

        await self.db.commit()

        logger.info(
            "Voizematic call.transcribed saved successfully. "
            "CallLog ID: %s, Call ID: %s, Duration: %s",
            call_log.id,
            call_id,
            call_log.call_duration,
        )


class VoizematicVoiceService:

    BASE_URL = settings.VOIZEMATIC_BASE_URL

    def __init__(self):
        self.api_key = settings.VOIZEMATIC_API_KEY

        if not self.api_key:
            raise RuntimeError("VOIZEMATIC_API_KEY is not configured.")

        if not self.BASE_URL:
            raise RuntimeError("VOIZEMATIC_BASE_URL is not configured.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def trigger_call(
        self,
        agent_id: int,
        to_number: str,
        knowledge_base_id: int | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:

        url = f"{self.BASE_URL}/calls"

        payload = {
            "to_number": to_number,
            "agent_id": agent_id,
        }

        if knowledge_base_id is not None:
            payload["knowledge_base_id"] = knowledge_base_id

        if context:
            if len(context) > 2000:
                raise HTTPException(
                    status_code=400,
                    detail="Call context cannot exceed 2000 characters.",
                )
            payload["context"] = context[:2000]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                )

            if response.is_error:
                try:
                    provider_error = response.json()
                except ValueError:
                    provider_error = response.text[:1000]

                raise HTTPException(
                    status_code=(
                        response.status_code if response.status_code < 500 else 502
                    ),
                    detail={
                        "message": "Failed to initiate call.",
                        "provider_status": response.status_code,
                        "provider_response": provider_error,
                    },
                )

            try:
                response_json = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail="Invalid response received from service.",
                )

            # Voizematic returns call_id inside data
            provider_data = response_json.get("data") or {}

            call_id = provider_data.get("call_id") or response_json.get("call_id")
            job_id = provider_data.get("job_id") or response_json.get("job_id")

            # call_id = response_json.get("call_id")

            if call_id is None:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Service did not return a call ID.",
                        "provider_response": response_json,
                    },
                )

            return {
                "success": True,
                "call_id": str(call_id),
                "job_id": provider_data.get("job_id"),
                "status": provider_data.get("status"),
                "response_json": response_json,
            }

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Voizematic request timed out.",
            )

        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Voizematic.",
            )
