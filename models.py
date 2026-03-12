from datetime import datetime
from typing import Any, List

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
            "config": self.config or {},
            "description": self.description,
            "active": self.active,
        }


class ValueVersion(Base):
    __tablename__ = "value_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
