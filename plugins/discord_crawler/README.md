# Discord Channel Crawler

A production-ready Discord data pipeline that polls channels via the REST API, stores all messages, users, embeds, attachments, and mentions in PostgreSQL, and processes them through a Redis Streams queue.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Crawler (app/)                        │
│                                                              │
│  ┌──────────────┐  every 10s   ┌─────────────────────────┐  │
│  │ crawl_target │ ──────────── │     ChannelCrawler       │  │
│  │   (Postgres) │              │  (REST API polling)      │  │
│  └──────────────┘              └────────────┬────────────┘  │
│                                             │ ?after=last_id │
│                                    Discord REST API v10       │
│                                             │                 │
│                                ┌────────────▼────────────┐   │
│                                │     Redis Stream         │   │
│                                │   discord:messages       │   │
│                                └────────────┬────────────┘   │
│                                             │                 │
│                                ┌────────────▼────────────┐   │
│                                │    Message Worker        │   │
│                                │  (consumer + DB upsert)  │   │
│                                └────────────┬────────────┘   │
│                                             │                 │
│                                ┌────────────▼────────────┐   │
│                                │      PostgreSQL           │   │
│                                │  discord_message + more  │   │
│                                └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### How it works

1. **Crawler** (`app/run_bot.py`) — runs every `CRAWL_INTERVAL` seconds (default: 10s):
   - Loads all active channels from `crawl_target` table
   - For each channel, queries `MAX(discord_message.id)` from DB as the cursor
   - If no messages exist, falls back to `MAX_HISTORY_DAYS` ago (default: 7 days)
   - Fetches new messages via `GET /channels/{id}/messages?after={cursor}&limit=100`
   - Pushes raw Discord API payloads to Redis Stream `discord:messages`

2. **Worker** (`app/run_worker.py`) — consumes from Redis Stream:
   - Uses consumer groups for reliability and crash recovery
   - Deduplicates messages via Redis SET before processing
   - Upserts users, server members, messages, mentions, attachments, and embeds to PostgreSQL
   - ACKs messages on success; dead-letters after 3 failures

---

## Project Structure

```
discord-crawlers/
├── app/
│   ├── config.py               # pydantic-settings config
│   ├── database.py             # async SQLAlchemy engine + get_session()
│   ├── bot/
│   │   ├── client.py           # ChannelCrawler — REST polling logic
│   │   └── events.py           # Gateway events (commented, reserved for future)
│   ├── backfill/
│   │   └── worker.py           # One-shot historical backfill
│   ├── models/
│   │   ├── server.py           # discord_server
│   │   ├── channel.py          # discord_channel
│   │   ├── thread.py           # discord_thread
│   │   ├── user.py             # discord_user
│   │   ├── member.py           # discord_server_member
│   │   ├── message.py          # discord_message
│   │   ├── mention.py          # discord_message_mention
│   │   ├── attachment.py       # discord_attachment
│   │   ├── embed.py            # discord_message_embed
│   │   └── crawl_target.py     # crawl_target
│   ├── queue/
│   │   ├── producer.py         # push to Redis Stream
│   │   └── consumer.py         # read from Redis Stream (consumer groups)
│   ├── workers/
│   │   └── message_worker.py   # parse + upsert to DB
│   ├── utils/
│   │   ├── dedup.py            # Redis SET deduplication
│   │   └── rate_limiter.py     # Discord 429 handling
│   ├── run_bot.py              # entry point: crawler
│   ├── run_worker.py           # entry point: consumer worker
│   └── run_backfill.py         # entry point: backfill
├── alembic/
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_embed.py
├── src/                        # legacy sync scripts (still functional)
│   ├── crawl_channel.py        # direct REST → DB crawl (no queue)
│   └── import_from_json.py     # import DiscordChatExporter JSON
├── scripts/
│   └── add_channel.py          # CLI: add a channel to crawl targets
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Database Schema

| Table                     | Description                                      |
| ------------------------- | ------------------------------------------------ |
| `discord_server`          | Guild / server info                              |
| `discord_channel`         | Channel info                                     |
| `discord_thread`          | Thread info                                      |
| `discord_user`            | User profiles                                    |
| `discord_server_member`   | Per-server nickname + roles                      |
| `discord_message`         | Message content, timestamps, reply refs          |
| `discord_message_mention` | Mentioned users per message                      |
| `discord_attachment`      | File attachment metadata (no download)           |
| `discord_message_embed`   | Full embed objects as JSONB, indexed by position |
| `crawl_target`            | Channels to crawl + backfill status cursor       |

---

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- A Discord bot token with **Message Content Intent** enabled in the [Developer Portal](https://discord.com/developers/applications)

### 1. Clone and install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_BOT=true

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/discord_crawler
REDIS_URL=redis://localhost:6379/0

CRAWL_INTERVAL=10       # seconds between poll cycles
MAX_HISTORY_DAYS=7      # how far back to crawl on first run
RATE_LIMIT_DELAY=0.5    # seconds between Discord API requests
BACKFILL_BATCH_SIZE=100
```

> **Bot vs user token:** Set `DISCORD_BOT=true` for bot tokens (recommended), `false` for user tokens.

### Getting Discord tokens and IDs

> **Warning:** Automating personal (user) accounts is technically against Discord's Terms of Service. **Use a user token at your own risk.** Prefer using a bot token.

#### Get the token for your personal account (user token)

1. Open Discord in your web browser and log in.
2. Open any server or direct message channel.
3. Press `Ctrl+Shift+I` (or `Cmd+Opt+I` on macOS) to open Developer Tools.
4. Navigate to the **Network** tab.
5. Press `Ctrl+R` (or `Cmd+R`) to reload the page.
6. Switch between a few channels to trigger network requests.
7. In the request list, search for a request whose path starts with `messages`.
8. Click that request and open the **Headers** panel on the right.
9. Scroll down to **Request Headers**.
10. Find the `authorization` header and copy its value — this is your **user token**.

#### Get the token for your bot (recommended)

The bot token is generated during bot creation. If you lost it, generate a new one:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Open your application's settings.
3. Navigate to the **Bot** section on the left.
4. Under **Token**, click **Reset Token**.
5. Click **Yes, do it!** and authenticate to confirm.

- **Important:** Integrations using the previous token will stop working until updated.
- Your bot needs to have the **Message Content Intent** enabled to read message content.

#### Get the ID of a server or channel

1. Open Discord.
2. Open **Settings**.
3. Go to the **Advanced** section.
4. Enable **Developer Mode**.
5. Right‑click on the server or channel you need and click **Copy Server ID** or **Copy Channel ID**.

### 3. Start infrastructure

```bash
docker compose up -d db redis
```

PostgreSQL will be available on port `5435`, Redis on `6379`.

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Add channels to crawl

Before starting the crawler, register the channels you want to track. You need the channel ID and server (guild) ID — both are Discord snowflake integers.

```bash
# Enable Developer Mode in Discord → right-click any channel → Copy Channel ID
python scripts/add_channel.py \
  --channel 1234567890123456789 \
  --server  9876543210987654321 \
  --name    general \
  --server-name "My Server"
```

You can add multiple channels by running this multiple times.

---

## Running

You need **two processes** running simultaneously: the crawler and the worker.

### Option A — Run locally (two terminals)

**Terminal 1 — Crawler** (polls Discord API, pushes to Redis):

```bash
python -m app.run_bot
```

**Terminal 2 — Worker** (consumes from Redis, writes to PostgreSQL):

```bash
python -m app.run_worker
```

### Option B — Run with Docker Compose

```bash
# Start everything (infra + crawler + worker)
docker compose up -d

# View logs
docker compose logs -f bot
docker compose logs -f worker
```

### Option C — Backfill historical messages

Run once to crawl all pending channels from the beginning (up to `MAX_HISTORY_DAYS`):

```bash
# Locally
python -m app.run_backfill --once

# Via Docker (one-shot container)
docker compose --profile backfill up backfill
```

---

## Configuration Reference

| Variable              | Default                    | Description                                            |
| --------------------- | -------------------------- | ------------------------------------------------------ |
| `DISCORD_TOKEN`       | _(required)_               | Bot or user token                                      |
| `DISCORD_BOT`         | `true`                     | `true` = bot token, `false` = user token               |
| `DATABASE_URL`        | _(required)_               | PostgreSQL async URL (`postgresql+asyncpg://...`)      |
| `REDIS_URL`           | `redis://localhost:6379/0` | Redis connection URL                                   |
| `CRAWL_INTERVAL`      | `10`                       | Seconds between polling cycles                         |
| `MAX_HISTORY_DAYS`    | `7`                        | Days to look back when a channel has no messages in DB |
| `RATE_LIMIT_DELAY`    | `0.5`                      | Minimum seconds between Discord API requests           |
| `BACKFILL_BATCH_SIZE` | `100`                      | Messages per API request (max 100)                     |

---

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → Bot
3. Under **Bot** → enable **Message Content Intent**
4. Copy the token → paste into `.env` as `DISCORD_TOKEN`
5. Invite the bot to your server with the `Read Message History` permission:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=65536&scope=bot
   ```

---

## Legacy Scripts (`src/`)

The `src/` directory contains the original synchronous scripts. They still work independently and do not use Redis or the async pipeline.

| Script                    | Usage                                     |
| ------------------------- | ----------------------------------------- |
| `src/crawl_channel.py`    | Direct REST → PostgreSQL crawl (no queue) |
| `src/import_from_json.py` | Import a DiscordChatExporter JSON export  |
| `src/check_db.py`         | Verify DB connection and schema           |
| `src/migrate.py`          | Apply `database/database-schema.sql`      |

```bash
# Example: crawl a channel directly to the legacy schema
python src/crawl_channel.py --channel 1234567890 --guild 9876543210
```

---

## Troubleshooting

**`401 Unauthorized`** — Token is invalid or expired. Check `DISCORD_TOKEN` and that `DISCORD_BOT` matches your token type.

**`403 Forbidden`** — Bot lacks `Read Message History` permission in that channel.

**`No active crawl targets`** — Run `scripts/add_channel.py` first to register channels.

**Worker not consuming** — Ensure `run_worker.py` is running alongside `run_bot.py`. The crawler only pushes to Redis; nothing gets written to DB without the worker.

**Alembic error: table already exists** — You may have applied the legacy schema from `database/database-schema.sql`. The two schemas are independent (different table names). Run `alembic upgrade head` in a fresh database named `discord_crawler`.
