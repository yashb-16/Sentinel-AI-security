from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class SourceRef(BaseModel):
    doc_id: str
    title: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
