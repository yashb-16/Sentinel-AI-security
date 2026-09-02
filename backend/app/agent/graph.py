import re
import uuid

from langgraph.graph import END, StateGraph

from app.agent.prompt_security import SECURITY_RULES, wrap_untrusted_document
from app.agent.state import AgentState
from app.db.models import ApprovalRequest
from app.policy.gateway import GatewayDecision, decide
from app.rag import llm as llm_module
from app.rag.retriever import retrieve_documents
from app.tools.registry import TOOL_DEFINITIONS_PROMPT, TOOLS

_TOOL_CALL_PATTERN = re.compile(r'^\s*TOOL_CALL:\s*(\w+)\((.*)\)\s*$', re.DOTALL)
_ARG_PATTERN = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def retrieve_node(state: AgentState) -> dict:
    documents = retrieve_documents(question=state["question"], user=state["user"], db=state["db"])
    return {"documents": documents}


def build_secured_prompt(question: str, documents: list) -> str:
    wrapped_docs = "\n\n".join(
        wrap_untrusted_document(doc.title, doc.content) for doc in documents
    )
    return (
        f"{SECURITY_RULES}\n\n"
        f"{TOOL_DEFINITIONS_PROMPT}\n\n"
        f"Reference material:\n{wrapped_docs}\n\n"
        f"Question: {question}"
    )


def generate_node(state: AgentState) -> dict:
    prompt = build_secured_prompt(state["question"], state["documents"])
    answer = llm_module.get_llm_provider().generate(prompt)
    return {"answer": answer}


def parse_tool_call(text: str):
    match = _TOOL_CALL_PATTERN.match((text or "").strip())
    if not match:
        return None
    tool_name = match.group(1)
    args = dict(_ARG_PATTERN.findall(match.group(2)))
    return tool_name, args


def handle_tool_request_node(state: AgentState) -> dict:
    """Never trusts the LLM's own reply as the final answer without
    checking, first, whether it's actually a tool request -- and if it
    is, routes it through the Gateway before anything executes. This is
    the project's golden rule made concrete: the LLM can only ask.
    """
    parsed = parse_tool_call(state["answer"])
    if parsed is None:
        return {}

    tool_name, args = parsed
    user = state["user"]
    db = state["db"]

    gateway_decision, risk = decide(tool_name=tool_name, args=args, user=user)

    if gateway_decision == GatewayDecision.DENY:
        return {"answer": "Sorry, that action is not allowed for your account."}

    if gateway_decision == GatewayDecision.REQUIRE_APPROVAL:
        approval = ApprovalRequest(
            id=uuid.uuid4(),
            tenant_id=user.tenant_id,
            requested_by_user_id=user.id,
            tool_name=tool_name,
            tool_args=args,
            risk_level=risk.value if risk else "high",
            status="pending",
        )
        db.add(approval)
        db.commit()
        return {
            "answer": (
                "This request has been flagged as sensitive and now requires "
                "approval from an admin before it can proceed."
            )
        }

    # ALLOW -- actually run the tool now.
    tool_fn = TOOLS[tool_name]
    result = tool_fn(**args, user=user, db=db)

    if result is None:
        return {"answer": "I couldn't find anything matching that request."}

    return {"answer": f"Done. Result: {result}"}


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("handle_tool_request", handle_tool_request_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "handle_tool_request")
    graph.add_edge("handle_tool_request", END)
    return graph.compile()
