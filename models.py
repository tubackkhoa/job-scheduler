from typing import Optional
from sqlalchemy import (
    Boolean,
    Engine,
    Integer,
    String,
    Text,
    CheckConstraint,
    select,
    text,
    Sequence,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, Session
from datetime import datetime

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


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, Sequence("jobs_id_seq"), primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plugin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[str] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


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


def create_value_version(db_engine: Engine, payload: dict):
    #  validate at model declaration
    assert "field_id" in payload, "field_id is required"
    with Session(db_engine) as session:
        value_version = ValueVersion(**payload)
        session.add(value_version)
        session.commit()
        session.refresh(value_version)

        return value_version.to_dict()


def get_value_versions(
    db_engine: Engine,
    field_id: str,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    with Session(db_engine) as session:
        stmt = select(ValueVersion).where(ValueVersion.field_id == field_id)
        if search:
            stmt = stmt.where(ValueVersion.name.ilike(f"%{search}%"))

        stmt = stmt.order_by(ValueVersion.created_at.desc()).limit(limit).offset(offset)
        versions = session.execute(stmt).scalars().all()

        return {
            "versions": [version.to_dict() for version in versions],
            "count": len(versions),
            "search": search,
            "limit": limit,
            "offset": offset,
        }


def get_latest_value_version(db_engine: Engine, field_id: str):
    with Session(db_engine) as session:
        stmt = (
            select(ValueVersion)
            .where(ValueVersion.field_id == field_id)
            .order_by(ValueVersion.updated_at.desc())
            .limit(1)
        )
        version = session.execute(stmt).scalar_one_or_none()

        if not version:
            raise Exception(f"No SQL version found for field_id: {field_id}")

        return version.to_dict()


def get_value_version(
    db_engine: Engine,
    version_id: int,
):
    with Session(db_engine) as session:
        version = session.get(ValueVersion, version_id)
        if not version:
            raise Exception(
                f"SQL version {version_id} not found",
            )
        return version.to_dict()


def update_value_version(
    db_engine: Engine,
    version_id: int,
    payload: dict,
):

    with Session(db_engine) as session:
        version = session.get(ValueVersion, version_id)
        if not version:
            raise Exception(
                f"SQL version {version_id} not found",
            )

        # Update fields if provided
        for field in payload.keys():
            if field in payload:
                setattr(version, field, payload[field])

        version.updated_at = datetime.now()
        session.commit()
        session.refresh(version)

        return version.to_dict()


def delete_value_version(db_engine: Engine, version_id: int):
    with Session(db_engine) as session:
        version = session.get(ValueVersion, version_id)
        if not version:
            raise Exception(
                f"SQL version {version_id} not found",
            )

        session.delete(version)
        session.commit()

        return {
            "success": True,
            "message": f"SQL version {version_id} deleted",
        }