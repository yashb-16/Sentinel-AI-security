"""The Gateway: the single place a tool request's final fate is decided.
Combines the Policy Engine (hard rules) and the Risk Engine (how risky)
into one of ALLOW / DENY / REQUIRE_APPROVAL. Nothing executes a tool
without going through this.
"""

import enum

from app.policy.policy_engine import PolicyDecision, evaluate_policy
from app.policy.risk_engine import RiskLevel, score_risk


class GatewayDecision(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


def decide(*, tool_name: str, args: dict, user) -> tuple[GatewayDecision, RiskLevel | None]:
    policy = evaluate_policy(tool_name=tool_name, args=args, user=user)
    if policy == PolicyDecision.DENY:
        return GatewayDecision.DENY, None

    risk = score_risk(tool_name=tool_name, args=args)
    if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return GatewayDecision.REQUIRE_APPROVAL, risk

    return GatewayDecision.ALLOW, risk
