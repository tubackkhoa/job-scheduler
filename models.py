from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Sequence,
    String,
    Text,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from enforcer import ExecutionContext, global_permission


class Base(DeclarativeBase):
    pass


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(Integer, Sequence("plugins_id_seq"), primary_key=True)
    package: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    interval: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "interval > 0",
            name="ck_plugins_interval_positive",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "package": self.package,
            "interval": self.interval,
            "description": self.description,
        }


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, Sequence("jobs_id_seq"), primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plugin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "plugin_id": self.plugin_id,
            "config": self.config,
            "description": self.description,
            "active": self.active,
        }


class ValueVersion(Base):
    __tablename__ = "value_versions"
    id: Mapped[int] = mapped_column(Integer, Sequence("value_versions_id_seq"), primary_key=True)
    field_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tags: Mapped[str | None] = mapped_column(Text)  # JSON stored as text

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "value": self.value,
            "is_active": self.is_active,
        }


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    username: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Embedded small role list
    roles: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )


class DAO:
    job_config_cache: Dict[int, Dict[str, Any]] = {}

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    # ---------- plugins ----------

    async def add_plugin(
        self, package: str, interval: int, description: Optional[str] = None
    ) -> int:
        async with self.session_factory() as session:
            plugin = Plugin(
                package=package,
                interval=interval,
                description=description,
            )
            session.add(plugin)
            await session.flush()
            await session.commit()
            return plugin.id

    async def get_plugin(self, plugin_id: int) -> Optional[Plugin]:
        async with self.session_factory() as session:
            return await session.get(Plugin, plugin_id)

    async def delete_plugin(self, plugin_id: int) -> tuple[str, list[int]]:
        deleted_job_ids: list[int] = []

        async with self.session_factory() as session:
            plugin = await session.get(Plugin, plugin_id)
            if not plugin:
                raise ValueError(f"Plugin with id {plugin_id} not found")

            package = plugin.package

            result = await session.execute(select(Job).where(Job.plugin_id == plugin_id))
            jobs = result.scalars().all()

            for job in jobs:
                deleted_job_ids.append(job.id)
                await session.delete(job)

            await session.delete(plugin)
            await session.commit()

        for job_id in deleted_job_ids:
            self.job_config_cache.pop(job_id, None)

        return package, deleted_job_ids

    # ---------- jobs ----------

    async def add_job(
        self,
        session_id: int,
        plugin_id: int,
        config: Dict[str, Any],
        description: Optional[str] = None,
    ) -> int:
        async with self.session_factory() as session:
            job = Job(
                session_id=session_id,
                plugin_id=plugin_id,
                config=config,
                active=False,
                description=description,
            )
            session.add(job)
            await session.commit()

            self.job_config_cache[job.id] = config
            return job.id

    async def update_job(
        self, job_id: int, config: Dict[str, Any], description: Optional[str] = None
    ):
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                return

            job.config = config
            if description:
                job.description = description

            self.job_config_cache[job.id] = config
            await session.commit()

    async def remove_job(self, job_id: int):
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                return

            await session.delete(job)
            await session.commit()

        self.job_config_cache.pop(job_id, None)

    async def activate_job(self, job_id: int):
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                return None

            job.active = True
            await session.commit()
            return job

    async def deactivate_job(self, job_id: int):
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                return None

            job.active = False
            await session.commit()
            return job

    async def get_job(self, job_id: int):
        async with self.session_factory() as session:
            return await session.get(Job, job_id)

    async def get_all_jobs(self):
        async with self.session_factory() as session:
            result = await session.execute(select(Job))
            return result.scalars().all()

    async def get_all_jobs_by_plugin(self, plugin_id: int):
        async with self.session_factory() as session:
            result = await session.execute(select(Job).where(Job.plugin_id == plugin_id))
            return result.scalars().all()

    # ---------- permissions ----------

    @global_permission("job")
    async def get_jobs_by_plugin_and_session(
        self,
        ctx: ExecutionContext,
        plugin_id: int,
        session_id: Optional[int] = None,
    ) -> list[Job]:
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.plugin_id == plugin_id)
            if session_id is not None:
                stmt = stmt.where(Job.session_id == session_id)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    @global_permission("job")
    async def get_all_plugins(self, ctx: ExecutionContext):
        async with self.session_factory() as session:
            result = await session.execute(select(Plugin))
            return result.scalars().all()

    # ---------- JSON / raw SQL ----------

    async def get_jobs_by_model_keys(self, model_keys: List[str]) -> List[Job]:
        if not model_keys:
            return []

        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    text(
                        """
                        SELECT * FROM jobs
                        WHERE (config::jsonb->>'model_key') = ANY(:model_keys)
                        """
                    ),
                    {"model_keys": model_keys},
                )

                return [Job(**row._mapping) for row in result]

            except Exception:
                result = await session.execute(select(Job))
                jobs = result.scalars().all()

                return [
                    job for job in jobs if job.config and job.config.get("model_key") in model_keys
                ]
