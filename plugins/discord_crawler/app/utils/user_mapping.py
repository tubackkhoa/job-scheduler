from __future__ import annotations

from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plugins.discord_crawler.app.models import DiscordUserExternalAccount

ExternalPlatform = Literal["x", "polymarket"]


async def upsert_external_account_mapping(
    session: AsyncSession,
    *,
    discord_user_id: int,
    platform: ExternalPlatform,
    account_identifier: str,
) -> DiscordUserExternalAccount:
    """Create or update mapping for a Discord user to an external account."""
    stmt = select(DiscordUserExternalAccount).where(
        DiscordUserExternalAccount.discord_user_id == discord_user_id,
        DiscordUserExternalAccount.platform == platform,
    )
    result = await session.execute(stmt)
    mapping: Optional[DiscordUserExternalAccount] = result.scalar_one_or_none()

    if mapping is None:
        mapping = DiscordUserExternalAccount(
            discord_user_id=discord_user_id,
            platform=platform,
            account_identifier=account_identifier,
        )
        session.add(mapping)
    else:
        mapping.account_identifier = account_identifier

    return mapping
