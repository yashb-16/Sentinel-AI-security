"""Output-side data-loss-prevention: a deterministic, non-LLM scan of the
final answer text before it reaches the user. Credentials always block
the whole answer; PII gets redacted in place; salary figures are
role-aware (only HR/admin see them unredacted).

Findings are category labels only ("credential", "email", ...) -- never
the actual matched value, since findings are what gets logged.
"""

import enum
import re
from dataclasses import dataclass, field

CREDENTIAL_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
SALARY_AMOUNT_PATTERN = re.compile(r"[\$₹]\s?[\d,]+(?:\.\d+)?")
SALARY_CONTEXT_KEYWORDS = ("salary", "compensation", "pay", "ctc")
PRIVILEGED_ROLES = {"hr", "admin"}


class DLPAction(str, enum.Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class DLPResult:
    action: DLPAction
    text: str
    findings: list = field(default_factory=list)


def scan_output(text: str, *, user) -> DLPResult:
    for pattern in CREDENTIAL_PATTERNS:
        if pattern.search(text):
            return DLPResult(
                action=DLPAction.BLOCK,
                text=(
                    "This response was blocked because it appeared to contain "
                    "credential-like content."
                ),
                findings=["credential"],
            )

    findings = []
    redacted = text

    if EMAIL_PATTERN.search(redacted):
        redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
        findings.append("email")

    if PHONE_PATTERN.search(redacted):
        redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
        findings.append("phone")

    text_lower = text.lower()
    has_salary_context = any(keyword in text_lower for keyword in SALARY_CONTEXT_KEYWORDS)
    if has_salary_context and SALARY_AMOUNT_PATTERN.search(redacted):
        if str(user.role) not in PRIVILEGED_ROLES:
            redacted = SALARY_AMOUNT_PATTERN.sub("[REDACTED_SALARY]", redacted)
            findings.append("salary")

    if findings:
        return DLPResult(action=DLPAction.REDACT, text=redacted, findings=findings)

    return DLPResult(action=DLPAction.ALLOW, text=text, findings=[])
