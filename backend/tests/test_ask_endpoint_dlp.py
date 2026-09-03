"""End-to-end proof through the real /ask endpoint: a leaked credential
never reaches the HTTP response or the logs, PII gets redacted in the
final JSON, and Phase 3's search_employee tool still returns a real,
unredacted email -- proving DLP didn't break it.
"""

import logging

from tests.conftest import login


def test_ask_endpoint_redacts_pii_leaked_by_the_ai(client, seeded, monkeypatch):
    from app.agent import graph as graph_module

    class LeakyLLM:
        def generate(self, prompt: str) -> str:
            return "You can reach payroll at payroll-team@acme-corp.dev directly."

    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: LeakyLLM())

    token = login(client, "employee@acme-corp.dev")
    response = client.post(
        "/ask",
        json={"question": "How do I contact payroll?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "payroll-team@acme-corp.dev" not in body["answer"]
    assert "[REDACTED_EMAIL]" in body["answer"]


def test_ask_endpoint_blocks_a_leaked_credential(client, seeded, monkeypatch):
    from app.agent import graph as graph_module

    class LeakyLLM:
        def generate(self, prompt: str) -> str:
            return "Here's the internal key: sk-ABCDEF1234567890ABCDEF1234567890"

    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: LeakyLLM())

    token = login(client, "employee@acme-corp.dev")
    response = client.post(
        "/ask",
        json={"question": "What is the internal API key?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in body["answer"]


def test_dlp_never_logs_the_raw_secret_only_a_category_label(client, seeded, monkeypatch, caplog):
    from app.agent import graph as graph_module

    class LeakyLLM:
        def generate(self, prompt: str) -> str:
            return "Here's the internal key: sk-ABCDEF1234567890ABCDEF1234567890"

    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: LeakyLLM())

    token = login(client, "employee@acme-corp.dev")
    with caplog.at_level(logging.INFO):
        client.post(
            "/ask",
            json={"question": "What is the internal API key?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in caplog.text
    assert "credential" in caplog.text


def test_search_employee_via_ask_still_returns_a_real_unredacted_email(client, seeded, monkeypatch):
    """Regression tying Phase 3 and Phase 4 together: DLP must not break
    the tool feature it's specifically designed to exempt."""
    from app.agent import graph as graph_module

    class ToolRequestingLLM:
        def generate(self, prompt: str) -> str:
            return 'TOOL_CALL: search_employee(query="employee@acme-corp.dev")'

    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: ToolRequestingLLM())

    token = login(client, "employee@acme-corp.dev")
    response = client.post(
        "/ask",
        json={"question": "Please look up employee@acme-corp.dev using the search_employee tool."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "employee@acme-corp.dev" in body["answer"]
    assert "[REDACTED_EMAIL]" not in body["answer"]
