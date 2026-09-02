"""The human-approval endpoints: only admins may decide a pending
request, approving actually executes the underlying tool (creating the
ticket for real), and everything stays scoped to the deciding admin's
own tenant.
"""

import uuid

from app.db.models import ApprovalRequest, Ticket
from tests.conftest import login


def _make_pending_approval(db_session, seeded, category="salary"):
    acme = seeded["tenants"]["acme"]
    acme_employee = seeded["users"]["acme_employee"]
    approval = ApprovalRequest(
        id=uuid.uuid4(),
        tenant_id=acme.id,
        requested_by_user_id=acme_employee.id,
        tool_name="create_ticket",
        tool_args={
            "subject": "Salary question",
            "description": "Question about my salary",
            "category": category,
        },
        risk_level="high",
        status="pending",
    )
    db_session.add(approval)
    db_session.commit()
    return approval


def test_non_admin_cannot_decide_an_approval(client, seeded, db_session):
    approval = _make_pending_approval(db_session, seeded)
    token = login(client, "employee@acme-corp.dev")

    response = client.post(
        f"/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_approving_actually_creates_the_ticket(client, seeded, db_session):
    approval = _make_pending_approval(db_session, seeded)
    token = login(client, "admin@acme-corp.dev")

    response = client.post(
        f"/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db_session.refresh(approval)
    assert approval.status == "approved"
    ticket = db_session.query(Ticket).filter(Ticket.category == "salary").first()
    assert ticket is not None


def test_admin_denying_never_creates_the_ticket(client, seeded, db_session):
    approval = _make_pending_approval(db_session, seeded)
    token = login(client, "admin@acme-corp.dev")

    response = client.post(
        f"/approvals/{approval.id}/decide",
        json={"decision": "deny"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db_session.refresh(approval)
    assert approval.status == "denied"
    ticket = db_session.query(Ticket).filter(Ticket.category == "salary").first()
    assert ticket is None


def test_admin_cannot_see_another_tenants_pending_approvals(client, seeded, db_session):
    globex = seeded["tenants"]["globex"]
    globex_employee = seeded["users"]["globex_employee"]
    globex_approval = ApprovalRequest(
        id=uuid.uuid4(),
        tenant_id=globex.id,
        requested_by_user_id=globex_employee.id,
        tool_name="create_ticket",
        tool_args={"subject": "s", "description": "d", "category": "salary"},
        risk_level="high",
        status="pending",
    )
    db_session.add(globex_approval)
    db_session.commit()

    token = login(client, "admin@acme-corp.dev")
    response = client.get("/approvals", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    approval_ids = {a["id"] for a in response.json()}
    assert str(globex_approval.id) not in approval_ids
