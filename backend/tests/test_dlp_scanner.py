"""The DLP scanner: a deterministic, non-LLM check on the final answer
text. Credentials always BLOCK the whole answer; PII gets REDACTED in
place; salary figures are role-aware (employees get them redacted, HR/
admin don't). Findings are category labels only -- never the actual
matched sensitive value, since those get logged.
"""

from app.dlp.scanner import DLPAction, scan_output


class FakeUser:
    def __init__(self, role):
        self.role = role


def test_credential_like_string_is_blocked():
    result = scan_output(
        "Here is an API key: sk-ABCDEF1234567890ABCDEF1234567890",
        user=FakeUser("employee"),
    )

    assert result.action == DLPAction.BLOCK
    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in result.text
    assert "credential" in result.findings


def test_email_is_redacted_but_rest_of_answer_survives():
    result = scan_output(
        "Contact John at john.doe@example.com for details.",
        user=FakeUser("employee"),
    )

    assert result.action == DLPAction.REDACT
    assert "john.doe@example.com" not in result.text
    assert "[REDACTED_EMAIL]" in result.text
    assert "Contact John at" in result.text
    assert "email" in result.findings


def test_phone_number_is_redacted():
    result = scan_output(
        "Call the helpdesk at 415-555-0134 for support.",
        user=FakeUser("employee"),
    )

    assert result.action == DLPAction.REDACT
    assert "415-555-0134" not in result.text
    assert "[REDACTED_PHONE]" in result.text
    assert "phone" in result.findings


def test_salary_figure_is_redacted_for_an_employee():
    result = scan_output(
        "Your salary is $120,000 per year.",
        user=FakeUser("employee"),
    )

    assert result.action == DLPAction.REDACT
    assert "$120,000" not in result.text
    assert "[REDACTED_SALARY]" in result.text
    assert "salary" in result.findings


def test_salary_figure_is_allowed_for_hr():
    result = scan_output(
        "Your salary is $120,000 per year.",
        user=FakeUser("hr"),
    )

    assert result.action == DLPAction.ALLOW
    assert "$120,000" in result.text
    assert result.findings == []


def test_salary_figure_is_allowed_for_admin():
    result = scan_output(
        "The salary band is $120,000 per year.",
        user=FakeUser("admin"),
    )

    assert result.action == DLPAction.ALLOW
    assert "$120,000" in result.text


def test_clean_text_with_nothing_sensitive_is_allowed_unchanged():
    text = "Acme employees get 20 days of paid vacation per year."

    result = scan_output(text, user=FakeUser("employee"))

    assert result.action == DLPAction.ALLOW
    assert result.text == text
    assert result.findings == []


def test_findings_never_contain_the_raw_sensitive_value():
    result = scan_output(
        "My email is jane@acme-corp.dev and my key is sk-ABCDEF1234567890ABCDEF1234567890",
        user=FakeUser("employee"),
    )

    joined_findings = " ".join(result.findings)
    assert "jane@acme-corp.dev" not in joined_findings
    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in joined_findings


# ---- Phase 4.1: coverage found by backend/scripts/benchmark_independent.py ----

import pytest  # noqa: E402


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-Ab3dEf9hIjKlMnOpQrStUvWxYz0123456789_-AbCdEfGhIjKlMnOpQrStUvWx",
        "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
        "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc",
        "AIza" + "SyA-1234567890abcdefghijklmnopqrstu",
        "xox" + "b-123456789012-123456789012-AbCdEfGhIjKlMnOpQrStUvWx",
        "ey" + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_modern_credential_formats_are_blocked(secret):
    result = scan_output(f"here you go: {secret}", user=FakeUser("employee"))

    assert result.action == DLPAction.BLOCK
    assert secret not in result.text


@pytest.mark.parametrize(
    "phone",
    [
        "+91 98765 43210",
        "(415) 555-0134",
        "+44 20 7946 0958",
        "01 23 45 67 89",
        "090-1234-5678",
        "001-415-555-0134x123",
    ],
)
def test_international_phone_formats_are_redacted(phone):
    result = scan_output(f"Call {phone} today.", user=FakeUser("employee"))

    assert phone not in result.text
    assert "phone" in result.findings


@pytest.mark.parametrize(
    "amount",
    ["£45,000", "€70,000", "USD 90000", "85k", "120000 dollars", "₹12,50,000", "Rs. 900000", "18 LPA"],
)
def test_more_salary_formats_are_redacted_for_an_employee(amount):
    result = scan_output(f"Their salary is {amount} per year.", user=FakeUser("employee"))

    assert amount not in result.text
    assert "salary" in result.findings


def test_salary_formats_still_visible_to_hr():
    result = scan_output("Their salary is £45,000 per year.", user=FakeUser("hr"))

    assert result.action == DLPAction.ALLOW


@pytest.mark.parametrize(
    "benign",
    [
        "Released on 2024-05-12 10:30 by the build server.",
        "Version 3.12.4 fixes the bug.",
        "The server is at 192.168.100.200 on the VPN.",
        "Order #123-456-7890123 has shipped.",
        "The meeting is on 12/05/2024 in room 415.",
        "The task-based learning approach is described in chapter 5.",
        "Build 20240512123456 finished in 45 seconds.",
        "About 5k users signed up, and 3 dollars were refunded.",
    ],
)
def test_hard_negatives_are_not_flagged(benign):
    result = scan_output(benign, user=FakeUser("employee"))

    assert result.action == DLPAction.ALLOW, result.findings
