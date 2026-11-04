from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CustomerList(Base):
    __tablename__ = "customer_lists"

    class SourceChoices:
        MANUAL = "MANUAL"
        FILE_IMPORT = "FILE_IMPORT"
        GOOGLE_SHEET = "GOOGLE_SHEET"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_customer_list_user_name",
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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        default=SourceChoices.FILE_IMPORT,
        nullable=False,
    )

    original_file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
        index=True,
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

    contacts = relationship(
        "CustomerListContact",
        back_populates="customer_list",
        cascade="all, delete-orphan",
    )


class CustomerListContact(Base):
    __tablename__ = "customer_list_contacts"

    __table_args__ = (
        UniqueConstraint(
            "customer_list_id",
            "customer_id",
            name="uq_customer_list_contact",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    customer_list_id: Mapped[int] = mapped_column(
        ForeignKey("customer_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    customer_list = relationship(
        "CustomerList",
        back_populates="contacts",
    )

    customer = relationship(
        "Customer",
        back_populates="customer_list_associations",
    )
