"""The Policy Engine: deterministic WHO/WHAT/WHICH rules. Answers only
ALLOW_CANDIDATE or DENY -- it never scores risk, and a DENY here is final,
nothing downstream gets consulted.
"""

import enum

KNOWN_TOOLS = {"search_employee", "create_ticket"}
PRIVILEGED_ROLES = {"hr", "admin"}


class PolicyDecision(str, enum.Enum):
    ALLOW_CANDIDATE = "allow_candidate"
    DENY = "deny"


def evaluate_policy(*, tool_name: str, args: dict, user) -> PolicyDecision:
    if tool_name not in KNOWN_TOOLS:
        return PolicyDecision.DENY

    if tool_name == "search_employee":
        query = (args.get("query") or "").strip().lower()
        if str(user.role) in PRIVILEGED_ROLES:
            return PolicyDecision.ALLOW_CANDIDATE
        # A plain employee may only look up their own record.
        if query and query == user.email.lower():
            return PolicyDecision.ALLOW_CANDIDATE
        return PolicyDecision.DENY

    if tool_name == "create_ticket":
        # Any authenticated user may file a ticket about themselves --
        # the Risk Engine, not the Policy Engine, decides how sensitive
        # its content is.
        return PolicyDecision.ALLOW_CANDIDATE

    return PolicyDecision.DENY
