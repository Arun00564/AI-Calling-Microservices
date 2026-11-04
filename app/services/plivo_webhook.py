from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.voice_call_logs import VoiceCallLog
from app.db.models.plivo_webhook_event import PlivoWebhookEvent

from app.tasks.voice_tasks import (
    process_completed_call_task,
)


class PlivoWebhookService:

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    def to_int(self, value):
        if value is None or value == "":
            return None

        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    async def process_event(
        self,
        payload: dict[str, Any],
    ):
        print("Processing Plivo webhook event:------", payload)
        # ==========================================
        # Extract Plivo object
        # ==========================================

        data = payload.get("data") or {}
        obj = data.get("object") or {}

        call_uuid = obj.get("call_uuid")
        event_name = obj.get("event_name")
        event_data = obj.get("event_data") or {}
        flow_run_uuid = obj.get("flow_run_uuid")

        # ==========================================
        # Validate webhook data
        # ==========================================

        if not flow_run_uuid:
            return {
                "success": False,
                "status": 400,
                "message": "flow_run_uuid missing in webhook.",
            }

        if not event_name:
            return {
                "success": False,
                "status": 400,
                "message": "event_name missing in webhook.",
            }

        # ==========================================
        # Check duplicate webhook
        # ==========================================

        event_result = await self.db.execute(
            select(PlivoWebhookEvent).where(
                PlivoWebhookEvent.flow_run_uuid == flow_run_uuid,
                PlivoWebhookEvent.event_name == event_name,
            )
        )

        existing_event = event_result.scalar_one_or_none()

        if existing_event:
            return {
                "success": True,
                "status": 200,
                "message": "Webhook already processed.",
                "duplicate": True,
                "event_name": event_name,
                "call_log_id": None,
            }

        # ==========================================
        # Find VoiceCallLog
        # ==========================================

        result = await self.db.execute(
            select(VoiceCallLog).where(VoiceCallLog.flow_run_uuid == flow_run_uuid)
        )

        call_log = result.scalar_one_or_none()

        if call_log is None:
            return {
                "success": False,
                "status": 404,
                "message": "VoiceCallLog not found.",
            }

        # ==========================================
        # Create webhook event
        # ==========================================

        webhook_event = PlivoWebhookEvent(
            flow_run_uuid=flow_run_uuid,
            event_name=event_name,
            call_uuid=call_uuid,
            payload=payload,
            status="processed",
        )

        self.db.add(webhook_event)

        # ==========================================
        # Common fields
        # ==========================================

        call_log.event_name = event_name
        call_log.call_uuid = call_uuid
        call_log.flow_uuid = obj.get("flow_uuid")
        call_log.flow_name = obj.get("flow_name")

        call_log.raw_event_data = event_data
        call_log.webhook_payload = payload

        # ==========================================
        # HANGUP
        # ==========================================

        if event_name == "hangup":

            call_log.call_status = self.get_value_by_suffix(
                event_data,
                "call_status",
            )

            # call_log.call_duration = event_data.get("call_duration")
            call_log.call_duration = self.to_int(event_data.get("call_duration"))
            call_log.hangup_source = event_data.get("hangup_source")
            # call_log.direction = event_data.get("Dial Lead.direction")
            call_log.direction = self.get_value_by_suffix(
                event_data,
                "direction",
            )
            call_log.hangup_data = event_data

        # ==========================================
        # RECORDING
        # ==========================================

        elif event_name == "recording":

            call_log.recording_url = event_data.get("recording_url")
            # call_log.recording_duration = event_data.get("recording_duration")
            call_log.recording_duration = self.to_int(
                event_data.get("recording_duration")
            )
            call_log.transcription = event_data.get("transcription")
            call_log.conversation_summary = event_data.get("conversation_summary")
            call_log.recording_data = event_data

        # ==========================================
        # Save
        # ==========================================

        await self.db.commit()

        await self.db.refresh(call_log)

        # ==========================================
        # Queue post-call processing
        # ==========================================

        if event_name == "hangup" and str(call_log.call_status).lower() == "completed":
            process_completed_call_task.delay(call_log.id)

        return {
            "success": True,
            "status": 200,
            "message": "Webhook processed successfully.",
            "event_name": event_name,
            "call_log_id": call_log.id,
        }

    @staticmethod
    def get_value_by_suffix(
        data: dict[str, Any],
        suffix: str,
    ):
        """
        Find a value where the key ends with the
        supplied suffix.

        Example:

        {
            "Dial Lead.call_status": "completed"
        }

        suffix = "call_status"

        returns:

        "completed"
        """

        for key, value in data.items():

            if key.endswith(suffix):
                return value

        return None
