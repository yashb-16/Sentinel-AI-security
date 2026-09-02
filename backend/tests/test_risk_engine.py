"""The Risk Engine only runs on requests the Policy Engine already let
through. It scores LOW/MEDIUM/HIGH/CRITICAL -- it never decides ALLOW vs
DENY itself, that's the Gateway's job.
"""

from app.policy.risk_engine import RiskLevel, score_risk


def test_search_employee_is_always_low_risk():
    risk = score_risk(tool_name="search_employee", args={"query": "anything"})

    assert risk == RiskLevel.LOW


def test_general_it_ticket_is_low_or_medium_risk():
    risk = score_risk(
        tool_name="create_ticket",
        args={"subject": "s", "description": "my laptop is slow", "category": "it"},
    )

    assert risk in (RiskLevel.LOW, RiskLevel.MEDIUM)


def test_salary_related_ticket_is_high_risk():
    risk = score_risk(
        tool_name="create_ticket",
        args={"subject": "s", "description": "question about my salary", "category": "salary"},
    )

    assert risk == RiskLevel.HIGH


def test_payroll_and_compensation_categories_are_high_risk():
    for category in ("payroll", "compensation", "hr_confidential"):
        risk = score_risk(
            tool_name="create_ticket",
            args={"subject": "s", "description": "d", "category": category},
        )
        assert risk == RiskLevel.HIGH


def test_unrecognized_category_fails_safe_to_high_risk():
    risk = score_risk(
        tool_name="create_ticket",
        args={"subject": "s", "description": "d", "category": "something_made_up"},
    )

    assert risk == RiskLevel.HIGH


def test_bulk_sounding_request_is_critical_risk():
    risk = score_risk(
        tool_name="create_ticket",
        args={
            "subject": "s",
            "description": "please export salary data for all employees",
            "category": "salary",
        },
    )

    assert risk == RiskLevel.CRITICAL
