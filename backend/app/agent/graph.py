from langgraph.graph import END, StateGraph

from app.agent.prompt_security import SECURITY_RULES, wrap_untrusted_document
from app.agent.state import AgentState
from app.rag import llm as llm_module
from app.rag.retriever import retrieve_documents


def retrieve_node(state: AgentState) -> dict:
    documents = retrieve_documents(question=state["question"], user=state["user"], db=state["db"])
    return {"documents": documents}


def build_secured_prompt(question: str, documents: list) -> str:
    wrapped_docs = "\n\n".join(
        wrap_untrusted_document(doc.title, doc.content) for doc in documents
    )
    return (
        f"{SECURITY_RULES}\n\n"
        f"{wrapped_docs}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the reference data above. If it doesn't contain "
        "the answer, say you don't know."
    )


def generate_node(state: AgentState) -> dict:
    prompt = build_secured_prompt(state["question"], state["documents"])
    answer = llm_module.get_llm_provider().generate(prompt)
    return {"answer": answer}


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
