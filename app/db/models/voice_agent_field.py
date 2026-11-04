from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class VoiceAgentField(Base):
    __tablename__ = "voice_agent_fields"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    voice_agent_id: Mapped[int] = mapped_column(
        ForeignKey(
            "voice_agents.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    field_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    field_label: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    voice_agent = relationship(
        "VoiceAgent",
        back_populates="agent_fields",
    )

    def __repr__(self) -> str:
        return f"<VoiceAgentField(id={self.id}, field_key={self.field_key}, voice_agent_id={self.voice_agent_id})>"
