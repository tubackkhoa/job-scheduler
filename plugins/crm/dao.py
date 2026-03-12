from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from enforcer import job_permission
from .models import session_factory, Contact, Lead, Deal, Activity


async def get_contacts():
    async with session_factory() as db:
        result = await db.execute(select(Contact).options(selectinload(Contact.company)))
        return result.scalars().all()


async def get_contact(contact_id):
    async with session_factory() as db:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        return result.scalar_one_or_none()


@job_permission("crm")
async def create_contact(ctx, name, email=None, phone=None, company_id=None):
    async with session_factory() as db:
        contact = Contact(
            name=name,
            email=email,
            phone=phone,
            company_id=company_id,
        )

        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return contact


@job_permission("crm")
async def delete_contact(ctx, contact_id):
    async with session_factory() as db:
        res = await db.execute(select(Contact).where(Contact.id == contact_id))
        contact = res.scalar_one_or_none()
        if not contact:
            return False

        await db.delete(contact)
        await db.commit()
        return True


async def get_deals():
    async with session_factory() as db:
        res = await db.execute(select(Deal))
        return res.scalars().all()


@job_permission("crm")
async def update_deal_stage(ctx, deal_id, stage):
    async with session_factory() as db:
        result = await db.execute(select(Deal).where(Deal.id == deal_id))
        deal = result.scalar_one_or_none()

        if not deal:
            return None

        deal.stage = stage
        await db.commit()

        return deal


@job_permission("crm")
async def create_deal(ctx, title, value, stage="prospecting"):
    async with session_factory() as db:
        deal = Deal(title=title, value=value, stage=stage)
        db.add(deal)
        await db.commit()
        await db.refresh(deal)
        return deal


async def get_leads():
    async with session_factory() as db:
        res = await db.execute(select(Lead))
        return res.scalars().all()


@job_permission("crm")
async def create_lead(ctx, name, email, source):
    async with session_factory() as db:
        lead = Lead(
            name=name,
            email=email,
            source=source,
        )

        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        return lead


@job_permission("crm")
async def convert_lead_to_deal(ctx, lead_id, company_id, value):
    async with session_factory() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return None

        deal = Deal(
            title=lead.name,
            value=value,
            stage="prospecting",
            company_id=company_id,
        )

        db.add(deal)
        lead.status = "converted"

        await db.commit()
        await db.refresh(deal)

        return deal


async def crm_dashboard():
    async with session_factory() as db:

        contacts = await db.scalar(select(func.count(Contact.id)))
        leads = await db.scalar(select(func.count(Lead.id)))
        deals = await db.scalar(select(func.count(Deal.id)))

        return {
            "contacts": contacts,
            "leads": leads,
            "deals": deals,
            "revenue": [
                {"month": "Jan", "value": 2000},
                {"month": "Feb", "value": 3500},
                {"month": "Mar", "value": 4200},
            ],
        }


async def crm_reports():
    async with session_factory() as db:

        deals = await db.execute(select(func.count()).select_from(Deal))
        total_deals = deals.scalar()

        revenue = await db.execute(select(func.sum(Deal.value)))
        total_revenue = revenue.scalar() or 0

        by_stage = await db.execute(select(Deal.stage, func.count()).group_by(Deal.stage))

        stages = [{"stage": s, "count": c} for s, c in by_stage.all()]

        return {
            "total_deals": total_deals,
            "revenue": total_revenue,
            "stages": stages,
        }


async def get_pipeline():
    async with session_factory() as db:
        result = await db.execute(select(Deal))
        deals = result.scalars().all()

        stages = {}

        for d in deals:
            stages.setdefault(d.stage, []).append(
                {
                    "id": d.id,
                    "title": d.title,
                    "value": d.value,
                    "stage": d.stage,
                    "company_id": d.company_id,
                }
            )

        return stages


async def get_activities():
    async with session_factory() as db:
        result = await db.execute(select(Activity).options(selectinload(Activity.contact)))
        return result.scalars().all()


@job_permission("crm")
async def create_activity(ctx, contact_id, type, subject, description, due_date=None):
    async with session_factory() as db:
        activity = Activity(
            contact_id=contact_id,
            type=type,
            subject=subject,
            description=description,
            due_date=due_date,
        )

        db.add(activity)
        await db.commit()
        await db.refresh(activity)

        return activity
