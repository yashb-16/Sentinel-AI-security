"""search_employee is scoped to the caller's own tenant by construction --
tenant_id always comes from the authenticated user object our own code
passes in, never from an argument the LLM could control. This test
proves that even when two tenants have people with clashing emails-ish
data, a search never crosses the tenant boundary.
"""

from app.tools.search_employee import search_employee


def test_finds_a_match_within_the_callers_own_tenant(db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]

    result = search_employee(query="hr@acme-corp.dev", user=acme_employee, db=db_session)

    assert result is not None
    assert result["email"] == "hr@acme-corp.dev"
    assert result["role"] == "hr"


def test_never_returns_a_match_from_a_different_tenant(db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]

    # This email only exists in Globex's tenant.
    result = search_employee(query="hr@globex-corp.dev", user=acme_employee, db=db_session)

    assert result is None


def test_never_leaks_the_hashed_password_field(db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]

    result = search_employee(query="hr@acme-corp.dev", user=acme_employee, db=db_session)

    assert "hashed_password" not in result
    assert "password" not in result
