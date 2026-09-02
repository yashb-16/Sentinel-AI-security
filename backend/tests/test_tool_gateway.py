"""The Gateway is the only place a final ALLOW/DENY/REQUIRE_APPROVAL
decision gets made -- it combines the Policy Engine (hard rules) and the
Risk Engine (how risky), and it's the one thing every tool request must
pass through before anything executes.
"""

from app.policy.gateway import GatewayDecision, decide


class FakeUser:
    def __init__(self, email, role, tenant_id="tenant-1"):
        self.email = email
        self.role = role
        self.tenant_id = tenant_id


def test_policy_deny_short_circuits_to_deny_regardless_of_risk():
    employee = FakeUser("employee@acme-corp.dev", "employee")

    decision, risk = decide(
        tool_name="search_employee", args={"query": "hr@acme-corp.dev"}, user=employee
    )

    assert decision == GatewayDecision.DENY


def test_low_risk_allowed_request_is_allowed():
    employee = FakeUser("employee@acme-corp.dev", "employee")

    decision, risk = decide(
        tool_name="create_ticket",
        args={"subject": "s", "description": "printer is broken", "category": "it"},
        user=employee,
    )

    assert decision == GatewayDecision.ALLOW


def test_high_risk_allowed_request_requires_approval():
    employee = FakeUser("employee@acme-corp.dev", "employee")

    decision, risk = decide(
        tool_name="create_ticket",
        args={"subject": "s", "description": "question about my salary", "category": "salary"},
        user=employee,
    )

    assert decision == GatewayDecision.REQUIRE_APPROVAL


def test_unknown_tool_is_denied_not_just_high_risk():
    employee = FakeUser("employee@acme-corp.dev", "employee")

    decision, risk = decide(tool_name="delete_everything", args={}, user=employee)

    assert decision == GatewayDecision.DENY
