from sqlalchemy import (
    Boolean,
    Integer,
    Text,
    CheckConstraint,
    text,
    Sequence,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
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


class SqlVersion(Base):
    __tablename__ = "sql_versions"

    id: Mapped[int] = mapped_column(Integer, Sequence("sql_versions_id_seq"), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tags: Mapped[str | None] = mapped_column(Text)  # JSON stored as text
