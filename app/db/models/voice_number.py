from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# class VoiceNumber(Base):
#     __tablename__ = "voice_numbers"

#     id: Mapped[int] = mapped_column(
#         primary_key=True,
#         index=True,
#     )

#     user_id: Mapped[int] = mapped_column(
#         ForeignKey("user_details.id", ondelete="CASCADE"),
#         nullable=False,
#         index=True,
#     )

#     phone_number: Mapped[str] = mapped_column(
#         String(20),
#         nullable=False,
#         index=True,
#     )

#     is_active: Mapped[bool] = mapped_column(
#         Boolean,
#         default=True,
#         nullable=False,
#     )

#     created_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         server_default=func.now(),
#         nullable=False,
#     )

#     updated_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         server_default=func.now(),
#         onupdate=func.now(),
#         nullable=False,
#     )

#     user = relationship(
#         "UserDetails",
#         back_populates="voice_numbers",
#     )

#     voice_agents = relationship(
#         "VoiceAgent",
#         back_populates="voice_numbers",
#         cascade="all, delete-orphan",
#     )

#     voice_calls = relationship(
#         "VoiceCallLog",
#         back_populates="from_number",
#     )

#     user_details = relationship(
#         "UserDetails",
#         back_populates="voice_numbers",
#     )

#     def __repr__(self) -> str:
#         return f"<VoiceNumber(id={self.id}, phone_number={self.phone_number}, user_id={self.user_id})>"


class VoiceNumber(Base):
    __tablename__ = "voice_numbers"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_number_id",
            name="uq_voice_number_provider_resource",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # New: identifies the calling provider
    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="plivo",
        server_default="plivo",
        index=True,
    )

    # New: external number ID returned by the provider
    # Keep nullable for existing Plivo records and compatibility.
    provider_number_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
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

    user_details = relationship(
        "UserDetails",
        back_populates="voice_numbers",
    )

    voice_agents = relationship(
        "VoiceAgent",
        back_populates="voice_numbers",
        cascade="all, delete-orphan",
    )

    voice_calls = relationship(
        "VoiceCallLog",
        back_populates="from_number",
    )

    def __repr__(self) -> str:
        return (
            f"<VoiceNumber("
            f"id={self.id}, "
            f"phone_number={self.phone_number}, "
            f"provider={self.provider}, "
            f"user_id={self.user_id})>"
        )
