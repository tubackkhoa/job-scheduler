from pathlib import Path

from pydantic_settings import BaseSettings

DATABASE_URL = f"sqlite+aiosqlite:///{Path(__file__).parent.with_name('discord_crawler.db')}"


class Settings(BaseSettings):
    DISCORD_TOKEN: str = ""
    DISCORD_BOT: bool = True
    DATABASE_URL: str = DATABASE_URL
    REDIS_URL: str = "redis://localhost:6379/0"
    BACKFILL_BATCH_SIZE: int = 100
    RATE_LIMIT_DELAY: float = 0.5
    CRAWL_INTERVAL: int = 10  # seconds between polling cycles
    MAX_HISTORY_DAYS: int = 7  # max lookback when no messages exist in DB

    # Sync DB URL for Alembic/backfill REST calls
    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "").replace("+aiopg", "")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
