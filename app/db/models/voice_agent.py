from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class VoiceAgent(Base):
    __tablename__ = "voice_agents"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # voice_number_id: Mapped[int] = mapped_column(
    #     ForeignKey("voice_numbers.id", ondelete="CASCADE"),
    #     nullable=False,
    #     index=True,
    # )

    voice_number_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice_numbers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    plivo_agent_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="plivo",
        server_default="plivo",
        index=True,
    )

    provider_agent_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    is_number_assigned: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Agent configuration fields
    type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    greeting: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    voice: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    knowledge_base_ids: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    booking_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Additional provider-specific configuration
    provider_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    input_schema: Mapped[list[Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    send_whatsapp_after_call_trigger: Mapped[bool] = mapped_column(
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

    user_details = relationship(
        "UserDetails",
        back_populates="voice_agents",
    )

    voice_numbers = relationship(
        "VoiceNumber",
        back_populates="voice_agents",
    )

    voice_calls = relationship(
        "VoiceCallLog",
        back_populates="voice_agent",
    )

    agent_fields = relationship(
        "VoiceAgentField",
        back_populates="voice_agent",
        cascade="all, delete-orphan",
    )

    campaigns = relationship(
        "Campaign",
        back_populates="voice_agent",
    )

    voice_call_queue = relationship(
        "VoiceCallQueue",
        back_populates="voice_agent",
    )

    def __repr__(self) -> str:
        return f"<VoiceAgent(id={self.id}, name={self.name}, user_id={self.user_id})>"
