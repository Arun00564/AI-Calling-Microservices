from sqlalchemy import select

from app.db.models.voice_call_logs import VoiceCallLog


class CallProcessingService:

    def __init__(self, db):
        self.db = db

    async def process_completed_call(
        self,
        call_log_id: int,
    ):

        result = await self.db.execute(
            select(VoiceCallLog).where(VoiceCallLog.id == call_log_id)
        )

        call_log = result.scalar_one_or_none()

        if not call_log:
            return {
                "success": False,
                "message": "Voice call log not found.",
            }

        print(f"Processing completed call: {call_log.id}")

        # ----------------------------------
        # Later we will add:
        #
        # AI summary
        # WhatsApp
        # analytics
        # etc.
        # ----------------------------------

        return {
            "success": True,
            "call_log_id": call_log.id,
            "message": "Call processed successfully.",
        }
