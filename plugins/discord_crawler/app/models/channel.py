from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordChannel(Base):
    __tablename__ = "discord_channel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_server.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="text")
