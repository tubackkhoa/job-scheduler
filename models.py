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
    cast,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from sqlalchemy.dialects.postgresql import JSONB

from enforcer import ADMIN_ROLE, ExecutionContext, global_permission


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

    def to_dict(self):
        return {
            "id": self.id,
            "roles": self.roles,
            "username": self.username,
        }


class SignalMessage(Base):
    __tablename__ = "signal_messages"

    id: Mapped[int] = mapped_column(Integer, Sequence("signal_messages_id_seq"), primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_key: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP")
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "model_key": self.model_key,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }


class DAO:
    job_config_cache: Dict[int, Dict[str, Any]] = {}
    user_roles_cache: dict[int, list[str]] = {}

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

    @global_permission("field")
    async def create_value_version(
        self,
        ctx: ExecutionContext,
        payload: dict,
    ) -> dict:
        assert "field_id" in payload, "field_id is required"

        async with self.session_factory() as session:
            value_version = ValueVersion(**payload)
            session.add(value_version)
            await session.commit()
            await session.refresh(value_version)
            return value_version.to_dict()

    @global_permission("field")
    async def get_value_version(
        self,
        ctx: ExecutionContext,
        version_id: int,
    ) -> dict:
        async with self.session_factory() as session:
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"SQL version {version_id} not found")

            return version.to_dict()

    async def get_latest(self, field_id: str) -> dict:
        async with self.session_factory() as session:
            stmt = (
                select(ValueVersion)
                .where(ValueVersion.field_id == field_id)
                .order_by(ValueVersion.updated_at.desc())
                .limit(1)
            )

            result = await session.execute(stmt)
            version = result.scalar_one_or_none()

            if not version:
                raise Exception(f"No SQL version found for field_id: {field_id}")

            return version.to_dict()

    @global_permission("field")
    async def get_value_versions(
        self,
        ctx: ExecutionContext,
        field_id: str,
        search: Optional[str] = None,
        id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        try:
            _, field_name = field_id.rsplit(".", 1)
        except ValueError:
            raise ValueError('field_id must be in format "{plugin_id}.{field_name}"')
        async with self.session_factory() as session:
            stmt = select(ValueVersion).where(
                func.substr(ValueVersion.field_id, func.instr(ValueVersion.field_id, ".") + 1)
                == field_name
            )
            if search:
                stmt = stmt.where(ValueVersion.name.ilike(f"%{search}%"))

            if id:
                stmt = stmt.where(ValueVersion.id == id)

            stmt = stmt.order_by(ValueVersion.created_at.desc()).limit(limit).offset(offset)

            result = await session.execute(stmt)
            versions = result.scalars().all()

            return {
                "versions": [v.to_dict() for v in versions],
                "count": len(versions),
                "search": search,
                "limit": limit,
                "offset": offset,
            }

    @global_permission("field")
    async def update_value_version(
        self,
        ctx: ExecutionContext,
        version_id: int,
        payload: dict,
    ) -> dict:
        async with self.session_factory() as session:
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"SQL version {version_id} not found")

            for field, value in payload.items():
                setattr(version, field, value)

            version.updated_at = datetime.now()
            await session.commit()
            await session.refresh(version)

            return version.to_dict()

    @global_permission("system")
    async def get_all_users(
        self,
        ctx: ExecutionContext,
    ) -> list:
        async with self.session_factory() as session:
            result = await session.execute(select(User.id, User.username, User.roles))
            rows = result.mappings().all()
            return list(rows)

    async def get_user_roles(self, user_id: int) -> list[str]:
        roles = self.user_roles_cache.get(user_id)
        if not roles:
            async with self.session_factory() as session:
                roles = await session.scalar(select(User.roles).where(User.id == user_id)) or []
                self.user_roles_cache[user_id] = roles
        return roles

    @global_permission("system")
    async def update_user_roles(
        self,
        ctx: ExecutionContext,
        user_id: int,
        roles: list[str],
    ) -> dict:

        if not roles:
            raise ValueError("User must have at least one role")

        async with self.session_factory() as session:
            # fetch user
            user = await session.get(User, user_id, with_for_update=True)
            if not user:
                raise ValueError("User not found")

            # prevent removing last admin
            if ADMIN_ROLE in user.roles:
                raise PermissionError("Cannot change the admin roles")

            # update roles only
            user.roles = roles
            # also update roles
            self.user_roles_cache[user_id] = roles

            await session.commit()
            await session.refresh(user)

            return user.to_dict()

    # ---------- dependency checking ----------

    async def get_jobs_depending_on_field(
        self,
        field_id: str,
        version_id: Optional[int] = None,
    ) -> List[dict]:
        # field_id = "{plugin_id}.{field_name}" but we only need field_name
        parts = field_id.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid field_id format: {field_id}, expected 'plugin_id.field_name'"
            )
        field_name = parts[1]
        try:
            async with self.session_factory() as session:
                cfg = cast(Job.config, JSONB)
                stmt = select(Job).where(Job.config.isnot(None))

                if version_id is None:
                    # config ? 'field_name'
                    stmt = stmt.where(cfg.has_key(field_name))
                else:
                    cfg_text = cfg.op("->>")(field_name)
                    stmt = stmt.where(cast(cfg_text, Integer) == version_id)

                result = await session.execute(stmt)
                jobs = result.scalars().all()
                return [
                    {
                        "job_id": j.id,
                        "description": j.description or "No description",
                        "config_value": (
                            (j.config or {}).get(field_name) if isinstance(j.config, dict) else None
                        ),
                        "session_id": j.session_id,
                        "plugin_id": j.plugin_id,
                    }
                    for j in jobs
                ]
        except Exception as e:
            print(e)
            return []

    async def get_jobs_depending_on_version(self, version_id: int) -> List[dict]:
        async with self.session_factory() as session:
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"ValueVersion {version_id} not found")

            field_id = version.field_id

        # Use the helper method to find dependent jobs
        dependent_jobs = await self.get_jobs_depending_on_field(field_id, version_id)
        for job in dependent_jobs:
            job["field_id"] = field_id
            job["field_name"] = field_id.split(".", 1)[1]
        return dependent_jobs

    # ---------- delete ----------

    async def delete_value_version(self, version_id: int) -> dict:
        dependent_jobs = await self.get_jobs_depending_on_version(version_id)

        updated_job_count = 0
        if dependent_jobs:
            field_name = dependent_jobs[0]["field_name"]

            async with self.session_factory() as session:
                for job_info in dependent_jobs:
                    job = await session.get(Job, job_info["job_id"])
                    if not job:
                        continue

                    # Handle both JSON string and dict
                    import json

                    if isinstance(job.config, str):
                        config = json.loads(job.config)
                    else:
                        config = job.config or {}

                    config[field_name] = 0
                    job.config = config
                    self.job_config_cache[job.id] = config
                    updated_job_count += 1

                await session.commit()

        async with self.session_factory() as session:
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"SQL version {version_id} not found")

            await session.delete(version)
            await session.commit()

            return {
                "success": True,
                "message": f"SQL version {version_id} deleted",
                "updated_jobs": updated_job_count,
            }

    @global_permission("job")
    async def apply_value_version_all_jobs(
        self, ctx: ExecutionContext, version_id: int, job_ids: List[int]
    ):
        async with self.session_factory() as session:
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"ValueVersion {version_id} not found")

            parts = version.field_id.split(".", 1)
            if len(parts) != 2:
                raise Exception(
                    f"Invalid field_id format: {version.field_id}, expected 'plugin_id.field_name'"
                )

            plugin_id_str, field_name = parts
            plugin_id = int(plugin_id_str)

            updated_count = 0

            for job_id in job_ids:
                job = await session.get(Job, job_id)
                if not job or not job.config:
                    continue

                # Handle both JSON string and dict
                import json

                if isinstance(job.config, str):
                    config = json.loads(job.config)
                else:
                    config = job.config

                config[field_name] = int(version_id)
                job.config = config
                self.job_config_cache[job.id] = config
                updated_count += 1

            await session.commit()

            return {
                "success": True,
                "updated_jobs": updated_count,
                "plugin_id": plugin_id,
                "field_name": field_name,
                "version_id": version_id,
            }

    async def save_signal_message(
        self,
        job_id: int,
        message: str,
        created_at: datetime,
    ) -> int:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise ValueError(f"Job with id {job_id} not found")

            model_key = job.config.get("model_key", None) if job.config else None
            signal = SignalMessage(
                job_id=job_id,
                message=message,
                captured_at=created_at,
                model_key=model_key,
                created_at=created_at,
            )
            session.add(signal)
            await session.commit()
            await session.refresh(signal)
            return signal.id

    async def get_signal_messages(
        self,
        job_id: int,
        limit: int = 100,
    ) -> List[dict]:
        async with self.session_factory() as session:
            stmt = (
                select(SignalMessage)
                .where(SignalMessage.job_id == job_id)
                .order_by(SignalMessage.captured_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            signals = result.scalars().all()
            return [s.to_dict() for s in signals]

    async def get_signal_messages_by_model(
        self,
        model_key: str,
        limit: int = 100,
    ) -> List[dict]:
        async with self.session_factory() as session:
            stmt = (
                select(SignalMessage)
                .where(SignalMessage.model_key == model_key)
                .order_by(SignalMessage.captured_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            signals = result.scalars().all()
            return [s.to_dict() for s in signals]
