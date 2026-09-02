"""Creates a support ticket. `user` and `db` come from the authenticated
session, never from LLM-supplied arguments -- a ticket is always
attributed to whoever is actually logged in, never to a name the LLM
(or something that tricked it) might try to supply instead.
"""

import uuid

from app.db.models import Ticket, User


def create_ticket(*, subject: str, description: str, category: str, user: User, db) -> dict:
    ticket = Ticket(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        subject=subject,
        description=description,
        category=category,
    )
    db.add(ticket)
    db.commit()
    return {"ticket_id": str(ticket.id), "status": "created"}
