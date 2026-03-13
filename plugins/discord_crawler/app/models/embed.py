from sqlalchemy import BigInteger, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from plugins.discord_crawler.app.models.base import Base


class DiscordMessageEmbed(Base):
    __tablename__ = "discord_message_embed"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord_message.id", ondelete="CASCADE"), nullable=False
    )
    embed_index: Mapped[int] = mapped_column(Integer, nullable=False)  # order in array
    data: Mapped[dict] = mapped_column(JSON, nullable=False)  # full embed object
