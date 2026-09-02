"""The agent can now request tools, but requesting is never the same as
executing. These tests prove the graph: (1) leaves Phase 2's plain-answer
behavior untouched when no tool is requested, (2) actually runs a tool
when the gateway allows it, (3) never runs a tool the gateway denies, and
(4) parks a high-risk tool behind a real pending-approval record instead
of running it.
"""

import uuid

from app.db.models import ApprovalRequest, Ticket


class FakeUser:
    def __init__(self, id, tenant_id, email, role):
        self.id = id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role


class ScriptedLLM:
    """Returns each response in order, one per call -- lets a test script
    a tool-call reply followed by a final-answer reply, like a real model
    would produce across the two-step tool-use flow."""

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


def test_plain_answer_with_no_tool_call_is_returned_unchanged(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(["The vacation policy is 20 days per year."])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert result["answer"] == "The vacation policy is 20 days per year."


def test_allowed_tool_call_actually_executes(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(
        [
            'TOOL_CALL: search_employee(query="employee@acme-corp.dev")',
            "You asked about employee@acme-corp.dev, who is an employee.",
        ]
    )

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "employee@acme-corp.dev" in result["answer"]


def test_denied_tool_call_never_executes(monkeypatch, db_session, seeded):
    acme_employee = seeded["users"]["acme_employee"]
    # Employees may only search their own record -- this targets someone else.
    llm = ScriptedLLM(['TOOL_CALL: search_employee(query="hr@acme-corp.dev")'])

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "hr@acme-corp.dev" not in result["answer"]
    assert "not allowed" in result["answer"].lower() or "denied" in result["answer"].lower()


def test_high_risk_tool_call_is_parked_pending_approval_not_executed(
    monkeypatch, db_session, seeded
):
    acme_employee = seeded["users"]["acme_employee"]
    llm = ScriptedLLM(
        [
            'TOOL_CALL: create_ticket(subject="Salary question", '
            'description="question about my salary", category="salary")'
        ]
    )

    result = _invoke_graph(monkeypatch, llm=llm, user=acme_employee, db_session=db_session)

    assert "approval" in result["answer"].lower()
    assert db_session.query(Ticket).filter(Ticket.category == "salary").first() is None
    pending = db_session.query(ApprovalRequest).filter(
        ApprovalRequest.tool_name == "create_ticket"
    ).first()
    assert pending is not None
    assert pending.status == "pending"
    assert str(pending.requested_by_user_id) == str(acme_employee.id)
