"""Looks up a coworker by email, scoped to the caller's own tenant.

`user` and `db` are always supplied by our own code from the
authenticated session -- never parsed from the LLM's tool-call
arguments. The LLM can only ever control `query`; it can never control
WHO is asking or WHICH tenant is searched.
"""

from app.db.models import User


def search_employee(*, query: str, user: User, db) -> dict | None:
    query = (query or "").strip().lower()
    if not query:
        return None

    match = (
        db.query(User)
        .filter(User.tenant_id == user.tenant_id)
        .filter(User.email == query)
        .first()
    )
    if match is None:
        return None

    return {"email": match.email, "role": str(match.role)}
