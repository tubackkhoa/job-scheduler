from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordThread(Base):
    __tablename__ = "discord_thread"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_channel.id"), nullable=False
    )
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_server.id"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    creator_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    parent_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
