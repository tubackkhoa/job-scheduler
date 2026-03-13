from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordUserExternalAccount(Base):
    """Mapping between a Discord user and external accounts (e.g., X, Polymarket)."""

    __tablename__ = "discord_user_external_account"
    __table_args__ = (
        UniqueConstraint(
            "discord_user_id",
            "platform",
            name="uq_discord_user_external_platform",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "x", "polymarket"
    account_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # e.g. handle, user id, wallet address
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
