from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class UserDetails(Base):
    __tablename__ = "user_details"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    mobile_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    voice_numbers = relationship(
        "VoiceNumber",
        back_populates="user_details",
        cascade="all, delete-orphan",
    )

    voice_agents = relationship(
        "VoiceAgent",
        back_populates="user_details",
        cascade="all, delete-orphan",
    )

    customers = relationship(
        "Customer",
        back_populates="user_details",
        cascade="all, delete-orphan",
    )

    voice_calls = relationship(
        "VoiceCallLog",
        back_populates="user_details",
    )

    campaigns = relationship(
        "Campaign",
        back_populates="user_details",
        cascade="all, delete-orphan",
    )

    voice_call_queue = relationship(
        "VoiceCallQueue",
        back_populates="user_details",
    )

    def __repr__(self) -> str:
        return f"<UserDetails(id={self.id}, user={self.first_name} {self.last_name}, email={self.email})>"
