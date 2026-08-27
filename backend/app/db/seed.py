"""Seeds two fictional tenants with users across all three roles and a mix
of general/hr_confidential documents, so manual testing and demos have
realistic cross-tenant, cross-role fixtures. Safe to re-run: skips seeding
if the tenants already exist.
"""

import uuid

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import Document, Role, Tenant, User

SEED_PASSWORD = "password123"


def seed_all(db: Session) -> None:
    if db.query(Tenant).filter(Tenant.slug == "acme").first() is not None:
        return

    acme = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme")
    globex = Tenant(id=uuid.uuid4(), name="Globex Corp", slug="globex")
    db.add_all([acme, globex])
    db.flush()

    def add_user(tenant: Tenant, role: Role, email: str) -> User:
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password(SEED_PASSWORD),
            role=role,
        )
        db.add(user)
        return user

    def add_doc(tenant: Tenant, title: str, content: str, classification: str,
                allowed_roles: list[str]) -> Document:
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title=title,
            content=content,
            classification=classification,
            allowed_roles=allowed_roles,
            qdrant_point_id=uuid.uuid4(),
        )
        db.add(doc)
        return doc

    for tenant, prefix, vacation_days, salary_band in (
        (acme, "Acme", 20, "140000 to 170000 USD"),
        (globex, "Globex", 15, "130000 to 160000 USD"),
    ):
        add_user(tenant, Role.EMPLOYEE, f"employee@{prefix.lower()}-corp.dev")
        add_user(tenant, Role.HR, f"hr@{prefix.lower()}-corp.dev")
        add_user(tenant, Role.ADMIN, f"admin@{prefix.lower()}-corp.dev")

        add_doc(
            tenant,
            f"{prefix} Vacation Policy",
            f"{prefix} employees get {vacation_days} days of paid vacation per year.",
            "general",
            ["employee", "hr", "admin"],
        )
        add_doc(
            tenant,
            f"{prefix} Remote Work Policy",
            f"{prefix} employees may work remotely up to 3 days per week.",
            "general",
            ["employee", "hr", "admin"],
        )
        add_doc(
            tenant,
            f"{prefix} Salary Bands",
            f"{prefix} engineering salary band L4 is {salary_band}.",
            "hr_confidential",
            ["hr", "admin"],
        )
        add_doc(
            tenant,
            f"{prefix} Performance Review Notes",
            f"{prefix} HR-confidential notes on the latest performance review cycle.",
            "hr_confidential",
            ["hr", "admin"],
        )

    db.commit()
