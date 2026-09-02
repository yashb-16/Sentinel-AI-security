"""create_ticket is the write tool: it must record the correct tenant and
creator (again, always server-injected from the authenticated user, never
LLM-supplied) and must actually persist a real Ticket row.
"""

from app.db.models import Ticket
from app.tools.create_ticket import create_ticket


def test_creates_a_ticket_with_the_callers_tenant_and_identity(db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]

    result = create_ticket(
        subject="Printer broken",
        description="The 3rd floor printer is jammed.",
        category="it",
        user=acme_employee,
        db=db_session,
    )

    assert result["status"] == "created"
    ticket = db_session.query(Ticket).filter(Ticket.id == result["ticket_id"]).first()
    assert ticket is not None
    assert str(ticket.tenant_id) == str(acme_employee.tenant_id)
    assert str(ticket.created_by_user_id) == str(acme_employee.id)
    assert ticket.category == "it"
