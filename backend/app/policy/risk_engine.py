"""The Risk Engine: scores anything the Policy Engine already allowed
through as LOW/MEDIUM/HIGH/CRITICAL. It never decides ALLOW vs DENY --
that combination happens one layer up, in the Gateway.
"""

import enum

HIGH_RISK_CATEGORIES = {"salary", "payroll", "compensation", "hr_confidential"}
KNOWN_LOW_RISK_CATEGORIES = {"it", "access_request", "general"}
BULK_MARKERS = ("all employees", "every employee", "entire company", "all staff")


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def score_risk(*, tool_name: str, args: dict) -> RiskLevel:
    if tool_name == "search_employee":
        return RiskLevel.LOW

    if tool_name == "create_ticket":
        category = (args.get("category") or "").strip().lower()
        description = (args.get("description") or "").strip().lower()

        if any(marker in description for marker in BULK_MARKERS):
            return RiskLevel.CRITICAL

        if category in HIGH_RISK_CATEGORIES:
            return RiskLevel.HIGH

        if category not in KNOWN_LOW_RISK_CATEGORIES:
            # Fail-safe: an unrecognized category is treated as risky
            # rather than assumed harmless.
            return RiskLevel.HIGH

        return RiskLevel.LOW

    # An unrecognized tool should never reach the Risk Engine (the Policy
    # Engine denies it first) -- but if it ever does, treat it as maximum
    # risk rather than silently defaulting to something low.
    return RiskLevel.CRITICAL
