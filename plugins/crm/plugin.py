import logging
from typing import Any, Callable, Dict
import pluggy

from pydantic import BaseModel, ConfigDict
from plugins.schema import ui_schema
from schemas import settings
from .models import init_db
from .seed import seed
from .dao import (
    get_contacts,
    create_contact,
    delete_contact,
    get_contact,
    crm_dashboard,
    crm_reports,
    get_activities,
    get_pipeline,
    update_deal_stage,
    get_leads,
    create_lead,
    convert_lead_to_deal,
    get_deals,
    create_deal,
)

hookimpl = pluggy.HookimplMarker("job-scheduler")


class Config(BaseModel):

    model_config = ConfigDict(
        json_schema_extra=ui_schema(
            {
                "url": (
                    "crm/Portal.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/portal.js"
                )
            }
        )
    )


class Plugin:

    _env = {
        "get_contacts": get_contacts,
        "create_contact": create_contact,
        "delete_contact": delete_contact,
        "get_contact": get_contact,
        "get_leads": get_leads,
        "create_lead": create_lead,
        "convert_lead_to_deal": convert_lead_to_deal,
        "get_deals": get_deals,
        "create_deal": create_deal,
        "crm_dashboard": crm_dashboard,
        "crm_reports": crm_reports,
        "get_activities": get_activities,
        "get_pipeline": get_pipeline,
        "update_deal_stage": update_deal_stage,
    }

    _routes = [
        (
            "",
            Config.model_config.get("json_schema_extra"),
        ),
        (
            "dashboard",
            {
                "url": (
                    "crm/Dashboard.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/dashboard.js"
                )
            },
        ),
        (
            "contacts",
            {
                "url": (
                    "crm/Contacts.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/contacts.js"
                )
            },
        ),
        (
            "contacts/:contact_id",
            {
                "url": (
                    "crm/Contact.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/contact.js"
                )
            },
        ),
        (
            "deals",
            {
                "url": (
                    "crm/Deals.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/deals.js"
                )
            },
        ),
        (
            "leads",
            {
                "url": (
                    "crm/Leads.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/leads.js"
                )
            },
        ),
        (
            "pipeline",
            {
                "url": (
                    "crm/Pipeline.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/pipeline.js"
                )
            },
        ),
        (
            "activities",
            {
                "url": (
                    "crm/Activities.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/activities.js"
                )
            },
        ),
        (
            "reports",
            {
                "url": (
                    "crm/Reports.tsx"
                    if settings.env == "dev"
                    else "{base_url}/assets/{package}/reports.js"
                )
            },
        ),
    ]

    @classmethod
    @hookimpl
    def routes(cls):
        return cls._routes

    @classmethod
    @hookimpl
    async def install(cls):
        await init_db()
        await seed()
        return True

    @classmethod
    @hookimpl
    def env(cls) -> Dict[str, Any]:
        return cls._env

    @classmethod
    @hookimpl
    def schema(cls, ctx):
        return Config.model_json_schema()

    @classmethod
    @hookimpl
    def config(cls, ctx, json=None, validate=False):
        return Config.model_validate(json or {}, context={"validate": validate})

    @classmethod
    @hookimpl
    def roles(cls):
        return {"crm_admin": ["crm"], "sales": ["crm"]}

    @classmethod
    @hookimpl
    async def run(cls, ctx, config, logger: logging.Logger, render: Callable):
        logger.info("CRM plugin running")
        return True
