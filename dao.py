from datetime import datetime
from typing import Any, Dict, List, Optional, Iterable

from sqlalchemy import (
    delete,
    or_,
    select,
    func,
)
from sqlalchemy.orm import InstrumentedAttribute, load_only
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from enforcer import ADMIN_ROLE, ExecutionContext, global_permission
from schemas import JobQuery
from models import Plugin, Job, ValueVersion, User, SignalMessage


class DAO:

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.plugin_cache: Dict[int, tuple[int, str, Optional[str]]] = {}
        self.job_config_cache: Dict[int, Dict[str, Any] | None] = {}
        self.user_cache: Dict[int, tuple[list[str], str]] = {}

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
            # add cache for plugin
            self.plugin_cache[plugin.id] = (interval, package, description)
            return plugin.id

    async def get_plugin(self, plugin_id: int) -> Optional[Plugin]:
        async with self.session_factory() as session:
            return await session.get(Plugin, plugin_id)

    async def delete_plugin(self, plugin_id: int) -> tuple[str, list[int]]:

        async with self.session_factory() as session:
            plugin = await session.get(Plugin, plugin_id)
            if not plugin:
                raise ValueError(f"Plugin with id {plugin_id} not found")

            package = plugin.package
            dialect = session.get_bind().dialect.name
            # optimizing for postgresql
            if dialect == "postgresql":
                # Single roundtrip, authoritative
                result = await session.execute(
                    delete(Job).where(Job.plugin_id == plugin_id).returning(Job.id)
                )
                job_ids = result.scalars().all()
            else:
                # Portable fallback
                result = await session.execute(select(Job.id).where(Job.plugin_id == plugin_id))
                job_ids = result.scalars().all()

                await session.execute(delete(Job).where(Job.plugin_id == plugin_id))

            await session.delete(plugin)
            await session.commit()

        # cache updates AFTER commit
        for job_id in job_ids:
            self.job_config_cache.pop(job_id, None)

        self.plugin_cache.pop(plugin_id, None)

        return package, list(job_ids)

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
            await session.commit()

            if job.active:
                self.job_config_cache[job.id] = config

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
            self.job_config_cache[job.id] = job.config
            job.active = True
            await session.commit()
            return job

    async def deactivate_job(self, job_id: int):
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if not job:
                return None
            self.job_config_cache.pop(job_id, None)
            job.active = False
            await session.commit()
            return job

    async def get_job(self, job_id: int):
        async with self.session_factory() as session:
            return await session.get(Job, job_id)

    async def get_all_jobs(self):
        async with self.session_factory() as session:
            result = await session.execute(select(Job))
            jobs = result.scalars().all()
            # cache active job config
            for job in jobs:
                if job.active:
                    self.job_config_cache[job.id] = job.config
            return jobs

    async def get_all_jobs_by_plugin(self, plugin_id: int):
        async with self.session_factory() as session:
            result = await session.execute(select(Job).where(Job.plugin_id == plugin_id))
            return result.scalars().all()

    @global_permission("system")
    async def get_jobs_by_filters(
        self,
        ctx: ExecutionContext,
        query: JobQuery,
        config: Optional[dict[str, list[int]]] = None,
    ) -> tuple[list[Job], int]:
        async with self.session_factory() as session:
            conditions = []
            # should avoid this kind of search
            if query.search_text:
                conditions.append(Job.description.ilike(f"%{query.search_text}%"))
            if query.active is not None:
                conditions.append(Job.active == query.active)
            if query.plugin_id:
                conditions.append(Job.plugin_id.in_(query.plugin_id))
            if query.session_id:
                conditions.append(Job.session_id.in_(query.session_id))

            # -----------------------------
            # JSONB filters (fully generic)
            # Anything here must exist in Job.config
            # -----------------------------
            if config:
                conditions.append(
                    or_(*(Job.config[key].as_string().in_(value) for key, value in config.items()))
                )

            where = [*conditions] if conditions else []

            # Count query
            count_stmt = select(func.count()).select_from(Job).where(*where)
            total = (await session.execute(count_stmt)).scalar() or 0

            # Data query
            stmt = select(Job).where(*where)

            if query.order_by:
                col = getattr(Job, query.order_by)
                stmt = stmt.order_by(col.desc() if query.sort == "desc" else col)

            if query.limit:
                stmt = stmt.limit(query.limit)

            if query.offset:
                stmt = stmt.offset(query.offset)

            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    # ---------- permissions ----------

    @global_permission("job")
    async def get_jobs_by_plugin_and_session(
        self,
        ctx: ExecutionContext,
        plugin_id: int,
        session_id: Optional[int] = None,
        include_fields: Optional[Iterable[InstrumentedAttribute]] = None,
    ) -> list[Job]:
        async with self.session_factory() as session:
            conditions = [Job.plugin_id == plugin_id]

            if session_id is not None:
                conditions.append(Job.session_id == session_id)

            stmt = select(Job).where(*conditions)

            if include_fields:
                stmt = stmt.options(load_only(*include_fields))

            result = await session.execute(stmt)
        return list(result.scalars().all())

    @global_permission("job")
    async def get_all_plugins(self, ctx: ExecutionContext):
        async with self.session_factory() as session:
            result = await session.execute(select(Plugin))
            plugins = result.scalars().all()
            # cache plugin info
            for plugin in plugins:
                self.plugin_cache[plugin.id] = (plugin.interval, plugin.package, plugin.description)

            return plugins

    # ---------- JSON / raw Value ----------

    async def get_jobs_by_model_keys(self, model_keys: List[str]) -> List[dict]:
        if not model_keys:
            return []

        async with self.session_factory() as session:
            condition = Job.config["model_key"].as_string().in_(model_keys)

            stmt = select(Job).where(condition)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            return [job.to_dict() for job in jobs]

    @global_permission("field")
    async def create_value_version(
        self,
        ctx: ExecutionContext,
        payload: dict,
    ) -> dict:
        if "field_id" not in payload:
            raise ValueError("field_id is required")

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
                raise Exception(f"Value version {version_id} not found")

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
                raise Exception(f"No Value version found for field_id: {field_id}")

            return version.to_dict()

    @global_permission("field")
    async def get_value_versions(
        self,
        ctx: ExecutionContext,
        field_id: str,
        search: Optional[str] = None,
        version_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        try:
            plugin_part, field_name = field_id.rsplit(".", 1)
        except ValueError:
            raise ValueError(
                'field_id must be in format "{plugin_id}.{field_name}" or *.{field_name}'
            )

        async with self.session_factory() as session:
            stmt = select(ValueVersion).where(
                ValueVersion.field_id.like(f"%.{field_name}")
                # if plugin_part == "*"
                # else ValueVersion.field_id == field_id
            )

            if search:
                stmt = stmt.where(ValueVersion.name.ilike(f"%{search}%"))

            if version_id:
                stmt = stmt.where(ValueVersion.id == version_id)

            stmt = stmt.order_by(ValueVersion.created_at.desc()).limit(limit).offset(offset)

            result = await session.execute(stmt)
            versions = result.scalars().all()

        return {
            "versions": [v.to_dict() for v in versions],
            "search": search,
            "limit": limit,
            "offset": offset,
        }

    async def get_value_versions_by_filters(
        self,
        ids: Optional[List[int]] = None,
    ) -> List[dict]:
        async with self.session_factory() as session:
            stmt = select(ValueVersion)
            if ids:
                stmt = stmt.where(ValueVersion.id.in_(ids))

            result = await session.execute(stmt)
            versions = result.scalars().all()
            return [v.to_dict() for v in versions]

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
                raise Exception(f"Value version {version_id} not found")

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
    ):
        async with self.session_factory() as session:
            result = await session.execute(select(User.id, User.username, User.roles))
            users = result.mappings().all()
            for user in users:
                self.user_cache[user.id] = (user.roles, user.username)
            return users

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
            self.user_cache[user_id] = (roles, user.username)

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
                stmt = select(Job).where(Job.config.isnot(None))
                expr = Job.config[field_name]
                stmt = stmt.where(
                    expr.as_integer() == version_id if version_id else expr.isnot(None)
                )

                result = await session.execute(stmt)
                jobs = result.scalars().all()
                return [
                    {
                        "job_id": j.id,
                        "description": j.description or "No description",
                        "config_value": (j.config or {}).get(field_name),
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
        async with self.session_factory() as session:
            # 1️⃣ Load version ONCE
            version = await session.get(ValueVersion, version_id)
            if not version:
                raise Exception(f"Value version {version_id} not found")

            try:
                _, field_name = version.field_id.split(".", 1)
            except ValueError:
                raise Exception(f"Invalid field_id format: {version.field_id}")

            # 2️⃣ Load all affected jobs in ONE query
            stmt = select(Job).where(
                Job.config.isnot(None),
                Job.config[field_name].as_integer() == version_id,
            )

            result = await session.execute(stmt)
            jobs = result.scalars().all()

            updated_job_count = 0

            for job in jobs:
                config = job.config or {}
                config[field_name] = 0
                job.config = config

                if job.active:
                    self.job_config_cache[job.id] = config

                updated_job_count += 1

            # 3️⃣ Delete version in SAME transaction
            await session.delete(version)
            await session.commit()

        return {
            "success": True,
            "message": f"Value version {version_id} deleted",
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

            result = await session.execute(select(Job).where(Job.id.in_(job_ids)))
            jobs = result.scalars().all()

            for job in jobs:
                config = job.config or {}
                config[field_name] = int(version_id)
                job.config = config
                if job.active:
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
            try:
                job = await session.get(Job, job_id)
                if not job:
                    raise ValueError(f"Job with id {job_id} not found")

                config = job.config or {}
                model_key = config.get("model_key", None)
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
            except Exception as e:
                print(f"Failed to save signal message: {str(e)}")
                return 0

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

    async def get_signal_messages_by_keys(
        self,
        model_keys: List[str],
        limit: int = 1000,
    ) -> List[dict]:
        if not model_keys:
            return []

        async with self.session_factory() as session:
            stmt = (
                select(SignalMessage)
                .where(SignalMessage.model_key.in_(model_keys))
                .order_by(SignalMessage.captured_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            signals = result.scalars().all()
            return [s.to_dict() for s in signals]

    async def get_signals_for_jobs(
        self,
        job_ids: List[int],
        limit_per_job: int = 5,
    ) -> Dict[int, List[dict]]:
        if not job_ids:
            return {}

        async with self.session_factory() as session:
            subq = (
                select(
                    SignalMessage,
                    func.row_number()
                    .over(
                        partition_by=SignalMessage.job_id, order_by=SignalMessage.captured_at.desc()
                    )
                    .label("rn"),
                )
                .where(SignalMessage.job_id.in_(job_ids))
                .subquery()
            )

            stmt = select(subq).where(subq.c.rn <= limit_per_job)

            try:
                result = await session.execute(stmt)
                rows = result.all()

                # Group by job_id
                signals_by_job: Dict[int, List[dict]] = {jid: [] for jid in job_ids}
                for row in rows:
                    sig_dict = {
                        "id": row.id,
                        "job_id": row.job_id,
                        "model_key": row.model_key,
                        "message": row.message,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                    }
                    if row.job_id in signals_by_job:
                        signals_by_job[row.job_id].append(sig_dict)

                return signals_by_job

            except Exception:
                stmt = (
                    select(SignalMessage)
                    .where(SignalMessage.job_id.in_(job_ids))
                    .order_by(SignalMessage.captured_at.desc())
                    .limit(len(job_ids) * limit_per_job)
                )
                result = await session.execute(stmt)
                signals = result.scalars().all()

                signals_by_job = {jid: [] for jid in job_ids}
                counts = {jid: 0 for jid in job_ids}

                for sig in signals:
                    if counts[sig.job_id] < limit_per_job:
                        signals_by_job[sig.job_id].append(sig.to_dict())
                        counts[sig.job_id] += 1

                return signals_by_job
