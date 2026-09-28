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
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),  # OpenAI legacy + project keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}"),  # Stripe
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),  # Google API key
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
]
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
# Candidate = run of digits/separators; _is_phone() filters out dates, IPs, ids.
_PHONE_CANDIDATE = re.compile(r"(?<![\w.])\+?\(?\d[\d ().-]{6,18}\d(?:\s?(?:x|ext\.?)\s?\d{1,5})?(?![\w])")
_NOT_PHONE = re.compile(r"^\d{4}-\d{2}-\d{2}|^\d{1,3}(?:\.\d{1,3}){3}$")
SALARY_AMOUNT_PATTERN = re.compile(
    r"(?:[\$₹£€¥]|\b(?:USD|INR|EUR|GBP|Rs\.?)\s?)\s?\d[\d,]*(?:\.\d+)?(?:\s?[kKmM]\b)?"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:k|K|dollars|rupees|euros|pounds|USD|INR|EUR|GBP|lakhs?|LPA)\b"
)
SALARY_CONTEXT_KEYWORDS = ("salary", "compensation", "pay", "ctc")
PRIVILEGED_ROLES = {"hr", "admin"}


def _is_phone(candidate: str) -> bool:
    number = re.split(r"\s?(?:x|ext)", candidate, maxsplit=1)[0]  # ignore an extension
    digits = sum(c.isdigit() for c in number)
    separators = sum(c in " ().-" for c in number)
    if not 9 <= digits <= 15 or _NOT_PHONE.match(number.strip()):
        return False
    if number.startswith("+"):
        return True
    # ponytail: heuristic -- without a '+', needs 2+ separators and no long digit group, so
    # bare digit runs and order/build ids pass through; a bare 10-digit phone is missed.
    # Swap in `phonenumbers` if that matters.
    return separators >= 2 and max(len(g) for g in re.findall(r"\d+", number)) <= 5


def _redact_phones(text: str) -> tuple[str, bool]:
    found = False

    def repl(m):
        nonlocal found
        if _is_phone(m.group(0)):
            found = True
            return "[REDACTED_PHONE]"
        return m.group(0)

    return _PHONE_CANDIDATE.sub(repl, text), found


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

    redacted, has_phone = _redact_phones(redacted)
    if has_phone:
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
