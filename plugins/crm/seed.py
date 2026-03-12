import random
from datetime import datetime, timedelta

from .models import (
    session_factory,
    init_db,
    Company,
    Contact,
    Lead,
    Deal,
    Activity,
    Note,
)


FIRST_NAMES = [
    "John",
    "Jane",
    "Alice",
    "Bob",
    "David",
    "Emma",
    "Michael",
    "Olivia",
    "Daniel",
    "Sophia",
    "Chris",
    "Lucas",
    "Mia",
    "Ethan",
    "Liam",
    "Ava",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Martinez",
    "Anderson",
]

COMPANIES = [
    "Acme Corp",
    "Globex",
    "Initech",
    "Umbrella",
    "Stark Industries",
    "Wayne Enterprises",
    "Cyberdyne",
    "Wonka Industries",
]

INDUSTRIES = [
    "Technology",
    "Finance",
    "Healthcare",
    "Retail",
    "Manufacturing",
]

SOURCES = ["website", "ads", "referral", "email", "conference"]

STAGES = [
    "prospecting",
    "qualified",
    "proposal",
    "won",
    "lost",
]

ACTIVITY_TYPES = ["call", "meeting", "email", "demo"]


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_email(name):
    return name.lower().replace(" ", ".") + "@example.com"


def random_phone():
    return f"+1-555-{random.randint(1000,9999)}"


async def seed():
    await init_db()

    async with session_factory() as db:

        companies = []
        contacts = []
        leads = []
        deals = []

        # ---- Companies ----
        for i in range(15):
            company = Company(
                name=random.choice(COMPANIES) + f" {i}",
                industry=random.choice(INDUSTRIES),
                website=f"https://company{i}.example.com",
            )

            db.add(company)
            companies.append(company)

        await db.flush()

        # ---- Contacts ----
        for _ in range(40):

            name = random_name()

            contact = Contact(
                name=name,
                email=random_email(name),
                phone=random_phone(),
                company_id=random.choice(companies).id,
            )

            db.add(contact)
            contacts.append(contact)

        await db.flush()

        # ---- Leads ----
        for _ in range(20):

            name = random_name()

            lead = Lead(
                name=name,
                email=random_email(name),
                source=random.choice(SOURCES),
                status=random.choice(["new", "contacted", "converted"]),
            )

            db.add(lead)
            leads.append(lead)

        await db.flush()

        # ---- Deals ----
        for _ in range(15):

            deal = Deal(
                title=f"{random.choice(['Enterprise','Platform','Cloud'])} Deal",
                value=random.randint(1000, 50000),
                stage=random.choice(STAGES),
                company_id=random.choice(companies).id,
            )

            db.add(deal)
            deals.append(deal)

        await db.flush()

        # ---- Activities ----
        for _ in range(30):

            activity = Activity(
                type=random.choice(ACTIVITY_TYPES),
                subject="Follow up",
                description="Customer follow-up discussion",
                contact_id=random.choice(contacts).id,
                due_date=datetime.utcnow() + timedelta(days=random.randint(-5, 10)),
            )

            db.add(activity)

        # ---- Notes ----
        for _ in range(30):

            entity_type = random.choice(["contact", "company", "deal"])

            if entity_type == "contact":
                entity_id = random.choice(contacts).id
            elif entity_type == "company":
                entity_id = random.choice(companies).id
            else:
                entity_id = random.choice(deals).id

            note = Note(
                entity_type=entity_type,
                entity_id=entity_id,
                content="Important note about this record",
            )

            db.add(note)

        await db.commit()

    print("✅ CRM seed complete (~100 records)")
