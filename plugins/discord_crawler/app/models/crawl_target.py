from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class CrawlTarget(Base):
    __tablename__ = "crawl_target"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_channel.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    backfill_status: Mapped[str] = mapped_column(String(50), default="pending")
    last_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("channel_id"),)
