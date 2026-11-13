from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class VoiceCallQueue(Base):
    __tablename__ = "voice_call_queue"

    __table_args__ = (
        Index(
            "ix_voice_call_queue_status_scheduled",
            "status",
            "scheduled_at",
        ),
        Index(
            "ix_voice_call_queue_user_status",
            "user_id",
            "status",
        ),
    )

    class StatusChoices:
        PENDING = "pending"
        PROCESSING = "processing"
        INITIATED = "initiated"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"

    class SourceChoices:
        MANUAL = "manual"
        BULK = "bulk"
        CAMPAIGN = "campaign"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ==========================================
    # Relationships / References
    # ==========================================

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_details.id", ondelete="CASCADE"),
        nullable=False,
    )

    voice_agent_id: Mapped[int] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )

    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )

    customer_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_lists.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ==========================================
    # Provider
    # ==========================================

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="plivo",
    )

    # ==========================================
    # Call Data
    # ==========================================

    call_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=SourceChoices.MANUAL,
    )

    # ==========================================
    # Queue Management
    # ==========================================

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=StatusChoices.PENDING,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ==========================================
    # Scheduling / Processing
    # ==========================================

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ==========================================
    # Call Log Reference
    # ==========================================

    voice_call_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice_call_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ==========================================
    # Timestamps
    # ==========================================

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

    # ==========================================
    # Relationships
    # ==========================================

    user_details = relationship("UserDetails", back_populates="voice_call_queue")

    voice_agent = relationship("VoiceAgent", back_populates="voice_call_queue")

    customer = relationship("Customer", back_populates="voice_call_queue")

    campaign = relationship("Campaign", back_populates="voice_call_queue")

    customer_list = relationship("CustomerList", back_populates="voice_call_queue")

    voice_call_log = relationship("VoiceCallLog", back_populates="voice_call_queue")
