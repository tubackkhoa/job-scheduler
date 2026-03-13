"""Message worker: processes raw Discord messages from Redis stream into PostgreSQL."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from plugins.discord_crawler.app.database import get_session
from plugins.discord_crawler.app.models import (
    DiscordAttachment,
    DiscordMessage,
    DiscordMessageEmbed,
    DiscordMessageMention,
    DiscordServerMember,
    DiscordUser,
)
from plugins.discord_crawler.app.utils.dedup import is_duplicate, mark_processed

logger = logging.getLogger(__name__)


def _bigint(v) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _parse_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def process_message(payload: dict, redis_client: Redis) -> None:
    """Process a single raw Discord API message payload.

    Steps:
    1. Dedup check
    2. Upsert discord_user (author)
    3. Upsert discord_server_member (nickname)
    4. Insert discord_message (ON CONFLICT DO NOTHING)
    5. Insert discord_message_mention rows
    6. Insert discord_attachment rows
    7. Insert discord_message_embed rows
    8. Mark as processed in dedup set
    """
    msg_id = _bigint(payload.get("id"))
    if not msg_id:
        logger.warning("Message missing id, skipping")
        return

    # 1. Dedup check
    if await is_duplicate(redis_client, msg_id):
        logger.debug("Duplicate message %s, skipping", msg_id)
        return

    author = payload.get("author") or {}
    author_id = _bigint(author.get("id"))
    if not author_id:
        logger.warning("Message %s has no author id, skipping", msg_id)
        return

    channel_id = _bigint(payload.get("channel_id"))
    guild_id = _bigint(payload.get("guild_id"))

    logger.info(
        "Processing msg_id=%s author_id=%s channel_id=%s",
        msg_id,
        author_id,
        channel_id,
    )

    async with get_session() as session:
        # 2. Upsert user
        await _upsert_user(session, author)

        # 3. Upsert server member
        if guild_id:
            member = payload.get("member") or {}
            await _upsert_member(session, guild_id, author_id, member)

        # 4. Insert message
        await _insert_message(session, payload, channel_id, msg_id, author_id)

        # 5. Insert mentions
        for mention_user in payload.get("mentions") or []:
            await _upsert_user(session, mention_user)
            mention_user_id = _bigint(mention_user.get("id"))
            if mention_user_id:
                await _insert_mention(session, msg_id, mention_user_id)

        # 6. Insert attachments
        for att in payload.get("attachments") or []:
            await _insert_attachment(session, msg_id, att)

        # 7. Insert embeds
        embeds = payload.get("embeds") or []
        if embeds:
            await _insert_embeds(session, msg_id, embeds)

    # 8. Mark processed
    await mark_processed(redis_client, msg_id)
    logger.debug("Processed message %s", msg_id)


async def _upsert_user(session: AsyncSession, user: dict) -> None:
    user_id = _bigint(user.get("id"))
    if not user_id:
        return
    stmt = (
        pg_insert(DiscordUser)
        .values(
            id=user_id,
            name=user.get("username") or user.get("name") or "unknown",
            is_bot=user.get("bot", False),
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"name": user.get("username") or user.get("name") or "unknown"},
        )
    )
    await session.execute(stmt)


async def _upsert_member(session: AsyncSession, guild_id: int, user_id: int, member: dict) -> None:
    nickname = member.get("nick") or member.get("display_name")
    roles = member.get("roles") or []
    joined_at = _parse_timestamp(member.get("joined_at"))
    stmt = (
        pg_insert(DiscordServerMember)
        .values(
            server_id=guild_id,
            user_id=user_id,
            nickname=nickname,
            roles=roles,
            joined_at=joined_at,
        )
        .on_conflict_do_update(
            constraint="discord_server_member_server_id_user_id_key",
            set_={
                "nickname": nickname,
                "roles": roles,
            },
        )
    )
    await session.execute(stmt)


async def _insert_message(
    session: AsyncSession,
    payload: dict,
    channel_id: int | None,
    msg_id: int,
    author_id: int,
) -> None:
    thread_id = None
    if payload.get("thread"):
        thread_id = _bigint(payload["thread"].get("id"))

    ref = payload.get("message_reference") or {}
    reference_message_id = _bigint(ref.get("message_id"))

    msg_type = payload.get("type", 0)
    type_names = {0: "default", 19: "reply", 7: "system"}
    type_str = type_names.get(msg_type, "default")

    timestamp = _parse_timestamp(payload.get("timestamp"))
    edited_at = _parse_timestamp(payload.get("edited_timestamp"))

    stmt = (
        pg_insert(DiscordMessage)
        .values(
            id=msg_id,
            channel_id=channel_id,
            thread_id=thread_id,
            author_id=author_id,
            reference_message_id=reference_message_id,
            content=payload.get("content") or "",
            type=type_str,
            timestamp=timestamp,
            edited_at=edited_at,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(stmt)


async def _insert_mention(session: AsyncSession, message_id: int, user_id: int) -> None:
    stmt = (
        pg_insert(DiscordMessageMention)
        .values(message_id=message_id, user_id=user_id)
        .on_conflict_do_nothing(constraint="discord_message_mention_message_id_user_id_key")
    )
    await session.execute(stmt)


async def _insert_attachment(session: AsyncSession, message_id: int, att: dict) -> None:
    att_id = _bigint(att.get("id"))
    if not att_id:
        return
    stmt = (
        pg_insert(DiscordAttachment)
        .values(
            id=att_id,
            message_id=message_id,
            filename=att.get("filename") or "unknown",
            content_type=att.get("content_type"),
            size=att.get("size"),
            width=att.get("width"),
            height=att.get("height"),
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(stmt)


async def _insert_embeds(session: AsyncSession, message_id: int, embeds: list[dict]) -> None:
    """Insert embed rows. Replaces existing embeds for this message (idempotent re-process)."""
    from sqlalchemy import delete
    from plugins.discord_crawler.app.models.embed import DiscordMessageEmbed

    # Delete existing embeds for this message first (safe: cascades from message)
    await session.execute(
        delete(DiscordMessageEmbed).where(DiscordMessageEmbed.message_id == message_id)
    )

    for idx, embed in enumerate(embeds):
        if not isinstance(embed, dict):
            continue
        stmt = pg_insert(DiscordMessageEmbed).values(
            message_id=message_id,
            embed_index=idx,
            data=embed,
        )
        await session.execute(stmt)
