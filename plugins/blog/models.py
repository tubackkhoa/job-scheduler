from pathlib import Path
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, declarative_base, mapped_column
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


DATABASE_URL = f"sqlite+aiosqlite:///{Path(__file__).with_name('blog.db')}"

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
session_factory = async_sessionmaker(engine, expire_on_commit=False)


Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
