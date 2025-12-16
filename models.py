from sqlalchemy import (
    Column,
    Integer,
    Text,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True)

    package = Column(Text, nullable=False, unique=True)

    interval = Column(Integer, nullable=False)

    description = Column(Text)

    __table_args__ = (
        CheckConstraint("interval > 0", name="ck_plugins_interval_positive"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    plugin_id = Column(Integer, nullable=False)
    description = Column(Text)
    config = Column(
        Text, CheckConstraint("json_valid(config)", name="ck_jobs_config_json")
    )

    active = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("active IN (0,1)", name="ck_jobs_active_bool"),
        UniqueConstraint("user_id", "plugin_id", name="uq_jobs_user_plugin"),
    )
