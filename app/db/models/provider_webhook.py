from datetime import datetime
from typing import Any

from sqlalchemy import (
    String,
    Text,
    JSON,
    Boolean,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base  # Use the same Base import as your other models


class ProviderWebhook(Base):
    __tablename__ = "provider_webhooks"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_account_key",
            name="uq_provider_webhook_account",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="voizematic"
    )

    # Identifies which provider account this registration belongs to.
    # "default" represents your centrally configured Voizematic account.
    provider_account_key: Mapped[str] = mapped_column(
        String(100), nullable=False, default="default"
    )

    webhook_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)

    events: Mapped[list[Any]] = mapped_column(JSON, nullable=False)

    # Store the encrypted secret, never the plain-text secret.
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
