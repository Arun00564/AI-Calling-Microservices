from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    class StatusChoices:
        DRAFT = "DRAFT"
        SCHEDULED = "SCHEDULED"
        QUEUED = "QUEUED"
        IN_PROGRESS = "IN_PROGRESS"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    class ScheduleChoices:
        NOW = "NOW"
        SCHEDULED = "SCHEDULED"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    voice_agent_id: Mapped[int] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=StatusChoices.DRAFT,
        server_default=StatusChoices.DRAFT,
        nullable=False,
        index=True,
    )

    schedule_type: Mapped[str] = mapped_column(
        String(20),
        default=ScheduleChoices.NOW,
        server_default=ScheduleChoices.NOW,
        nullable=False,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_contacts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    queued_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    completed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
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
        back_populates="campaigns",
    )

    voice_agent = relationship(
        "VoiceAgent",
        back_populates="campaigns",
    )

    customer_list = relationship(
        "CustomerList",
        back_populates="campaigns",
    )

    contacts = relationship(
        "CampaignContact",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    voice_calls = relationship(
        "VoiceCallLog",
        back_populates="campaign",
    )

    voice_call_queue = relationship(
        "VoiceCallQueue",
        back_populates="campaign",
    )
