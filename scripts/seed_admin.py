import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import User
from auth import pwd_context
from dotenv import load_dotenv
from schemas import settings
import os


load_dotenv()


async def seed_admin():
    engine = create_async_engine(
        settings.db_connection,
        echo=False,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        res = await session.execute(select(User).where(User.username == os.getenv("ADMIN_USER")))
        if res.scalar_one_or_none():
            return

        session.add(
            User(
                username=os.getenv("ADMIN_USER"),
                password=pwd_context.hash(settings.admin_password),
                roles=["admin"],
            )
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_admin())
