from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.voice_agent import VoiceAgent


class VoiceAgentRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_agent_for_user(
        self,
        agent_id: int,
        user_id: int,
    ) -> VoiceAgent | None:

        result = await self.db.execute(
            select(VoiceAgent)
            .options(selectinload(VoiceAgent.voice_number))
            .where(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == user_id,
                VoiceAgent.is_active.is_(True),
            )
        )

        return result.scalar_one_or_none()
