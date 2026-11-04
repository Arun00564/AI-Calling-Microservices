from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class PlivoWebhookEvent(Base):
    __tablename__ = "plivo_webhook_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    flow_run_uuid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    event_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    call_uuid: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="processed",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "flow_run_uuid",
            "event_name",
            name="uq_plivo_flow_event",
        ),
    )
