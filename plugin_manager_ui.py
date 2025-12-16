from datetime import datetime
from typing import Optional
from pytz import timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.job import Job
from apscheduler.events import (
    EVENT_ALL,
    JobExecutionEvent,
    JobSubmissionEvent,
    SchedulerEvent,
)

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import Session, declarative_base

import os
from pathlib import Path


def get_datetime_now() -> datetime:
    if tz := os.environ.get("TZ"):
        return datetime.now(timezone(tz))
    return datetime.now()


Base = declarative_base()


class APSEvent(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(255))
    job_name = Column(String(255))
    event_type = Column(String(50))
    info = Column(String(2000))
    timestamp = Column(DateTime, default=get_datetime_now)


class ScheduleManager:
    def __init__(
        self,
        app: FastAPI,
        scheduler: BaseScheduler,
        path: str = "/schedule",
        db_connection: str = "sqlite:///data/apscheduler_events.db",
        require_authentication: bool = True,
        apikey: Optional[str] = None,
    ):
        self.app = app
        self.scheduler = scheduler
        self.HOME_PATH = path
        self.AUTHENTICATE = require_authentication

        if self.AUTHENTICATE:
            self.API_KEY = apikey or os.environ.get("SM_UI_APIKEY")
            if not self.API_KEY:
                raise ValueError("Could not retrieve API key for ScheduleManager!")

        self.engine = create_engine(db_connection)
        Base.metadata.create_all(self.engine)  # ❌ no drop_all

        self.base_path = Path(__file__).parent

        self._init_endpoints()
        self._init_event_listeners()

    # ---------------------------
    # API ENDPOINTS
    # ---------------------------

    def _init_endpoints(self):

        def last_execution(job_id: str):
            with Session(self.engine) as session:
                event = (
                    session.query(APSEvent)
                    .filter_by(job_id=job_id, event_type="EVENT_JOB_EXECUTED")
                    .order_by(APSEvent.timestamp.desc())
                    .first()
                )
                return event.timestamp.isoformat() if event else None

        @self.app.get(self.HOME_PATH)
        async def list_jobs():
            jobs = self.scheduler.get_jobs()
            jobs.sort(key=lambda j: j.id)

            return {
                "jobs": [
                    {
                        "id": j.id,
                        "name": j.name or j.func.__name__,
                        "next_run_time": (
                            j.next_run_time.isoformat() if j.next_run_time else None
                        ),
                        "paused": j.next_run_time is None,
                        "last_execution": last_execution(j.id),
                    }
                    for j in jobs
                ]
            }

        @self.app.post(f"{self.HOME_PATH}/toggle/{{job_id}}")
        async def toggle_job(request: Request, job_id: str):
            if self.AUTHENTICATE:
                api_key = request.headers.get("Authorization")
                if api_key != self.API_KEY:
                    raise HTTPException(status_code=403, detail="Invalid API key")

            job = self.scheduler.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            if job.next_run_time is None:
                job.resume()
                state = "resumed"
            else:
                job.pause()
                state = "paused"

            return {"job_id": job_id, "state": state}

        @self.app.get(f"{self.HOME_PATH}/logs")
        async def logs():
            with Session(self.engine) as session:
                events = (
                    session.query(APSEvent)
                    .order_by(APSEvent.timestamp.desc())
                    .limit(500)
                    .all()
                )

            return {
                "events": [
                    {
                        "id": e.id,
                        "job_id": e.job_id,
                        "job_name": e.job_name,
                        "event_type": e.event_type,
                        "info": e.info,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in events
                ]
            }

    # ---------------------------
    # APSCHEDULER EVENT LISTENER
    # ---------------------------

    def _init_event_listeners(self):

        EVENT_MAP = {
            2**0: "EVENT_SCHEDULER_START",
            2**1: "EVENT_SCHEDULER_SHUTDOWN",
            2**2: "EVENT_SCHEDULER_PAUSED",
            2**3: "EVENT_SCHEDULER_RESUMED",
            2**9: "EVENT_JOB_ADDED",
            2**10: "EVENT_JOB_REMOVED",
            2**11: "EVENT_JOB_MODIFIED",
            2**12: "EVENT_JOB_EXECUTED",
            2**13: "EVENT_JOB_ERROR",
            2**14: "EVENT_JOB_MISSED",
            2**15: "EVENT_JOB_SUBMITTED",
        }

        def resolve_event_type(code: int) -> str:
            for mask, name in EVENT_MAP.items():
                if code & mask:
                    return name
            return f"UNKNOWN({code})"

        def job_listener(event: SchedulerEvent):
            args = {
                "event_type": resolve_event_type(event.code),
                "timestamp": get_datetime_now(),
            }

            if isinstance(event, (JobSubmissionEvent, JobExecutionEvent)):
                args["job_id"] = event.job_id
                job = self.scheduler.get_job(event.job_id)
                if job:
                    args["job_name"] = job.name or job.func.__name__

            if isinstance(event, JobExecutionEvent):
                if event.retval is not None:
                    args["info"] = str(event.retval)
                if event.exception:
                    args["info"] = f"{event.exception}\n{event.traceback}"

            with Session(self.engine) as session:
                session.add(APSEvent(**args))
                session.commit()

        self.scheduler.add_listener(job_listener, EVENT_ALL)
