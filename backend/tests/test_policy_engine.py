"""The Policy Engine answers hard WHO/WHAT/WHICH questions with a simple
ALLOW_CANDIDATE or DENY -- it never scores "how risky," that's the Risk
Engine's job. A DENY here is final; nothing downstream gets consulted.
"""

from app.policy.policy_engine import PolicyDecision, evaluate_policy


class FakeUser:
    def __init__(self, email, role, tenant_id="tenant-1"):
        self.email = email
        self.role = role
        self.tenant_id = tenant_id


def test_employee_can_search_their_own_email():
    user = FakeUser("employee@acme-corp.dev", "employee")

    decision = evaluate_policy(
        tool_name="search_employee", args={"query": "employee@acme-corp.dev"}, user=user
    )

    assert decision == PolicyDecision.ALLOW_CANDIDATE


def test_employee_cannot_search_someone_else():
    user = FakeUser("employee@acme-corp.dev", "employee")

    decision = evaluate_policy(
        tool_name="search_employee", args={"query": "hr@acme-corp.dev"}, user=user
    )

    assert decision == PolicyDecision.DENY


def test_hr_can_search_anyone():
    user = FakeUser("hr@acme-corp.dev", "hr")

    decision = evaluate_policy(
        tool_name="search_employee", args={"query": "employee@acme-corp.dev"}, user=user
    )

    assert decision == PolicyDecision.ALLOW_CANDIDATE


def test_admin_can_search_anyone():
    user = FakeUser("admin@acme-corp.dev", "admin")

    decision = evaluate_policy(
        tool_name="search_employee", args={"query": "employee@acme-corp.dev"}, user=user
    )

    assert decision == PolicyDecision.ALLOW_CANDIDATE


def test_any_authenticated_role_can_create_a_ticket():
    for role in ("employee", "hr", "admin"):
        user = FakeUser(f"{role}@acme-corp.dev", role)
        decision = evaluate_policy(
            tool_name="create_ticket",
            args={"subject": "s", "description": "d", "category": "it"},
            user=user,
        )
        assert decision == PolicyDecision.ALLOW_CANDIDATE


def test_unknown_tool_is_denied():
    user = FakeUser("employee@acme-corp.dev", "employee")

    decision = evaluate_policy(tool_name="delete_everything", args={}, user=user)

    assert decision == PolicyDecision.DENY
