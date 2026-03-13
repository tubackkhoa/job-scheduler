from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordServerMember(Base):
    __tablename__ = "discord_server_member"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_server.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord_user.id"), nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    roles: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("server_id", "user_id"),)
