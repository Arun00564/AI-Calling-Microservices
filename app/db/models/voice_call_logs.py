from uuid import UUID
from sqlalchemy import UUID

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class VoiceCallLog(Base):
    __tablename__ = "voice_call_logs"

    # =========================================================
    # Primary Key
    # =========================================================

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    # =========================================================
    # Ownership
    # =========================================================

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    voice_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Plivo IDs
    # =========================================================

    call_uuid: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    flow_run_uuid: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    flow_uuid: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    flow_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="plivo",
        server_default="plivo",
        index=True,
    )

    provider_call_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Call Information
    # =========================================================

    from_number_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice_numbers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    to_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    call_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    organisation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    product_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    feature_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    call_duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    hangup_source: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    direction: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # =========================================================
    # Call Variables
    # =========================================================

    call_variables: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # =========================================================
    # AI Output
    # =========================================================

    recording_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    recording_duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    transcription: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    conversation_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =========================================================
    # Webhook / Debug Data
    # =========================================================

    event_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    raw_event_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    hangup_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    recording_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    webhook_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # =========================================================
    # WhatsApp
    # =========================================================

    is_whatsapp_sent: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # =========================================================
    # Timestamps
    # =========================================================

    queue_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    initiated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    # =========================================================
    # Relationships
    # =========================================================

    user_details = relationship(
        "UserDetails",
        back_populates="voice_calls",
    )

    customer = relationship(
        "Customer",
        back_populates="voice_calls",
    )

    voice_agent = relationship(
        "VoiceAgent",
        back_populates="voice_calls",
    )

    from_number = relationship(
        "VoiceNumber",
        back_populates="voice_calls",
    )

    campaign = relationship(
        "Campaign",
        back_populates="voice_calls",
    )

    def __repr__(self) -> str:
        return f"<VoiceCallLog(id={self.id}, flow_run_uuid={self.flow_run_uuid}], customer_id={self.customer_id})>"
