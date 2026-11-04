from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.voice_call import VoiceCallLog


class VoiceCallRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        user_id: int,
        customer_id: int,
        voice_agent_id: int,
        from_number_id: int | None,
        to_number: str,
        call_variables: dict[str, Any],
        flow_run_uuid: str | None = None,
        flow_uuid: str | None = None,
        call_status: str = "initiated",
    ) -> VoiceCallLog:

        call_log = VoiceCallLog(
            user_id=user_id,
            customer_id=customer_id,
            voice_agent_id=voice_agent_id,
            from_number_id=from_number_id,
            to_number=to_number,
            call_variables=call_variables,
            flow_run_uuid=flow_run_uuid,
            flow_uuid=flow_uuid,
            call_status=call_status,
        )

        self.db.add(call_log)

        await self.db.flush()

        return call_log
