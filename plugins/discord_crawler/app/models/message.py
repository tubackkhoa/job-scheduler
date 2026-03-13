from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordMessage(Base):
    __tablename__ = "discord_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_channel.id"), nullable=False
    )
    thread_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("discord_thread.id"), nullable=True
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_user.id"), nullable=False
    )
    reference_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="default")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
