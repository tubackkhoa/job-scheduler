"""Discord Gateway event handlers (reserved for future use).

This module is NOT active. The current crawler uses REST API polling (ChannelCrawler).
Uncomment and wire into run_bot.py if you want to switch to or augment with Gateway events.

To re-enable:
    1. Install discord.py: pip install discord.py>=2.3.0
    2. In run_bot.py, replace ChannelCrawler with CrawlerBot and call setup_events(bot)
    3. Set MESSAGE_CONTENT and GUILDS intents in the Developer Portal
"""

# from __future__ import annotations
#
# import logging
# from datetime import datetime, timezone
#
# import discord
# from sqlalchemy.dialects.postgresql import insert as pg_insert
#
# from plugins.discord_crawler.app.bot.client import CrawlerBot
# from plugins.discord_crawler.app.database import get_session
# from plugins.discord_crawler.app.models.thread import DiscordThread
# from plugins.discord_crawler.app.models.message import DiscordMessage
# from plugins.discord_crawler.app.queue.producer import push_message
#
# logger = logging.getLogger(__name__)
#
#
# def setup_events(bot: CrawlerBot) -> None:
#     """Register all event handlers on the bot."""
#
#     @bot.event
#     async def on_ready():
#         logger.info("Bot connected as %s (id=%s)", bot.user, bot.user.id)
#         logger.info("Tracking %d channels", len(bot.active_channel_ids))
#
#     @bot.event
#     async def on_message(message: discord.Message):
#         if not bot.is_tracked_channel(message.channel.id):
#             return
#         payload = _message_to_payload(message)
#         await push_message(bot.redis_client, payload)
#         logger.debug("Queued message %s from #%s", message.id, message.channel)
#
#     @bot.event
#     async def on_message_edit(before: discord.Message, after: discord.Message):
#         if not bot.is_tracked_channel(after.channel.id):
#             return
#         try:
#             async with get_session() as session:
#                 stmt = (
#                     pg_insert(DiscordMessage)
#                     .values(
#                         id=after.id,
#                         channel_id=after.channel.id,
#                         author_id=after.author.id,
#                         content=after.content,
#                         type="default",
#                         timestamp=after.created_at,
#                         edited_at=after.edited_at or datetime.now(timezone.utc),
#                     )
#                     .on_conflict_do_update(
#                         index_elements=["id"],
#                         set_={
#                             "content": after.content,
#                             "edited_at": after.edited_at or datetime.now(timezone.utc),
#                         },
#                     )
#                 )
#                 await session.execute(stmt)
#             logger.debug("Updated edited message %s", after.id)
#         except Exception:
#             logger.exception("Failed to update edited message %s", after.id)
#
#     @bot.event
#     async def on_thread_create(thread: discord.Thread):
#         if not bot.is_tracked_channel(thread.parent_id):
#             return
#         try:
#             async with get_session() as session:
#                 stmt = pg_insert(DiscordThread).values(
#                     id=thread.id,
#                     channel_id=thread.parent_id,
#                     server_id=thread.guild.id,
#                     name=thread.name,
#                     creator_user_id=thread.owner_id,
#                     parent_message_id=thread.id if thread.id != thread.parent_id else None,
#                     created_at=thread.created_at,
#                 ).on_conflict_do_update(
#                     index_elements=["id"],
#                     set_={"name": thread.name},
#                 )
#                 await session.execute(stmt)
#             logger.info("Upserted thread %s (%s)", thread.id, thread.name)
#         except Exception:
#             logger.exception("Failed to upsert thread %s", thread.id)
#
#
# def _message_to_payload(message: discord.Message) -> dict:
#     """Convert a discord.py Message to a raw API-like dict for the queue."""
#     payload = {
#         "id": str(message.id),
#         "channel_id": str(message.channel.id),
#         "guild_id": str(message.guild.id) if message.guild else None,
#         "author": {
#             "id": str(message.author.id),
#             "username": message.author.name,
#             "discriminator": message.author.discriminator,
#             "bot": message.author.bot,
#         },
#         "content": message.content,
#         "timestamp": message.created_at.isoformat(),
#         "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
#         "type": message.type.value,
#         "pinned": message.pinned,
#         "mentions": [
#             {"id": str(u.id), "username": u.name, "bot": u.bot}
#             for u in message.mentions
#         ],
#         "attachments": [
#             {
#                 "id": str(a.id),
#                 "filename": a.filename,
#                 "content_type": a.content_type,
#                 "size": a.size,
#                 "width": a.width,
#                 "height": a.height,
#             }
#             for a in message.attachments
#         ],
#     }
#
#     if message.author and hasattr(message.author, "nick"):
#         payload["member"] = {
#             "nick": getattr(message.author, "nick", None),
#             "roles": [str(r.id) for r in getattr(message.author, "roles", [])],
#             "joined_at": (
#                 message.author.joined_at.isoformat()
#                 if hasattr(message.author, "joined_at") and message.author.joined_at
#                 else None
#             ),
#         }
#
#     if message.reference:
#         payload["message_reference"] = {
#             "message_id": str(message.reference.message_id) if message.reference.message_id else None,
#             "channel_id": str(message.reference.channel_id) if message.reference.channel_id else None,
#             "guild_id": str(message.reference.guild_id) if message.reference.guild_id else None,
#         }
#
#     return payload
