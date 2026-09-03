"""DLP is wired into the graph as its own final node -- but it must only
ever touch the AI's own raw generated prose, never a structured message
our own code produced (a tool result, a denial, a pending-approval
notice). Otherwise it would break the very tools Phase 3 built (e.g.
search_employee legitimately returning an email).
"""


class FakeUser:
    def __init__(self, id, tenant_id, email, role):
        self.id = id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, prompt: str) -> str:
        return self._responses.pop(0)


def _invoke_graph(monkeypatch, *, llm, user, documents=None, db_session=None):
    from app.agent import graph as graph_module

    monkeypatch.setattr(graph_module, "retrieve_documents", lambda **kwargs: documents or [])
    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: llm)

    agent = graph_module.build_agent_graph()
    return agent.invoke(
        {"question": "irrelevant", "user": user, "db": db_session, "documents": [], "answer": ""}
    )


def test_plain_ai_answer_containing_an_email_gets_redacted(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(["You can reach the office at contact@acme-corp.dev for more info."])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "contact@acme-corp.dev" not in result["answer"]
    assert "[REDACTED_EMAIL]" in result["answer"]


def test_plain_ai_answer_containing_a_credential_gets_blocked(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(["Use this key to authenticate: sk-ABCDEF1234567890ABCDEF1234567890"])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in result["answer"]


def test_tool_result_containing_an_email_is_not_redacted(monkeypatch, db_session, seeded):
    """The exemption that keeps Phase 3 working: search_employee's own,
    already-authorized email result must survive untouched."""
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(['TOOL_CALL: search_employee(query="employee@acme-corp.dev")'])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "employee@acme-corp.dev" in result["answer"]
    assert "[REDACTED_EMAIL]" not in result["answer"]


def test_denial_message_is_left_untouched(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    # Employees may only search their own record -- this targets someone else.
    llm = ScriptedLLM(['TOOL_CALL: search_employee(query="hr@acme-corp.dev")'])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert result["answer"] == "Sorry, that action is not allowed for your account."
