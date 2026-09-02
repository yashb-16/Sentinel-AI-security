"""The project's golden rule made concrete: the LLM never makes the
security decision, it can only ask. This simulates a "compromised" LLM --
as if it had been talked into it by a prompt-injection attempt from
Phase 2 -- deliberately requesting a forbidden action. The Gateway must
block it regardless of what the LLM wanted, independent of whether
Phase 2's defense should have already prevented the LLM from wanting it
in the first place.
"""

from app.db.models import ApprovalRequest, Ticket


class FakeUser:
    def __init__(self, id, tenant_id, email, role):
        self.id = id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role


class CompromisedLLM:
    """Always tries to request a forbidden action, as if a poisoned
    document had successfully tricked it -- regardless of what was
    actually asked."""

    def generate(self, prompt: str) -> str:
        return 'TOOL_CALL: search_employee(query="hr@acme-corp.dev")'


def test_gateway_blocks_a_forbidden_tool_request_even_from_a_compromised_llm(
    monkeypatch, db_session, seeded
):
    from app.agent import graph as graph_module

    acme_employee = seeded["users"]["acme_employee"]
    monkeypatch.setattr(graph_module, "retrieve_documents", lambda **kwargs: [])
    monkeypatch.setattr(graph_module.llm_module, "get_llm_provider", lambda: CompromisedLLM())

    agent = graph_module.build_agent_graph()
    result = agent.invoke(
        {
            "question": "What does this poisoned document say?",
            "user": acme_employee,
            "db": db_session,
            "documents": [],
            "answer": "",
        }
    )

    # The forbidden search never actually ran, and nothing about the HR
    # user's record leaked into the final answer.
    assert "hr@acme-corp.dev" not in result["answer"]
    # No side effect of any kind occurred -- not even a pending record,
    # since this was a hard policy DENY, not a require-approval case.
    assert db_session.query(ApprovalRequest).count() == 0
    assert db_session.query(Ticket).count() == 0
