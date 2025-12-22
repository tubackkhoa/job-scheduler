from sqlalchemy import (
    Column,
    Integer,
    Text,
    CheckConstraint,
    text,
    Sequence,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(Integer, Sequence("plugins_id_seq"), primary_key=True)
    package = Column(Text, nullable=False, unique=True)
    interval = Column(Integer, nullable=False)
    description = Column(Text)

    __table_args__ = (
        CheckConstraint("interval > 0", name="ck_plugins_interval_positive"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, Sequence("jobs_id_seq"), primary_key=True)
    user_id = Column(Integer, nullable=False)
    plugin_id = Column(Integer, nullable=False)
    description = Column(Text)
    config = Column(Text, nullable=True)
    active = Column(Integer, nullable=False, server_default=text("1"))

    __table_args__ = (CheckConstraint("active IN (0,1)", name="ck_jobs_active_bool"),)
