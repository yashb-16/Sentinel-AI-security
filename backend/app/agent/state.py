from typing import TypedDict


class AgentState(TypedDict):
    question: str
    user: object
    db: object
    documents: list
    answer: str
    answer_is_structured: bool
