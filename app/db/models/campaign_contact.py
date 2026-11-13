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


class CampaignContact(Base):
    __tablename__ = "campaign_contacts"

    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "customer_id",
            name="uq_campaign_customer",
        ),
    )

    class StatusChoices:
        PENDING = "PENDING"
        QUEUED = "QUEUED"
        INITIATING = "INITIATING"
        INITIATED = "INITIATED"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        SKIPPED = "SKIPPED"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=StatusChoices.PENDING,
        server_default=StatusChoices.PENDING,
        nullable=False,
        index=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    last_call_at: Mapped[datetime | None] = mapped_column(
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

    campaign = relationship(
        "Campaign",
        back_populates="contacts",
    )

    customer = relationship(
        "Customer",
        back_populates="campaign_associations",
    )
