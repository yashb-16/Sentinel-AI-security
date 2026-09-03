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
