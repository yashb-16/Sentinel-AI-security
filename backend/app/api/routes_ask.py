from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.rag import llm as llm_module
from app.rag.retriever import retrieve_documents
from app.schemas.ask import AskRequest, AskResponse, SourceRef

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    documents = retrieve_documents(question=payload.question, user=current_user, db=db)

    context = "\n\n".join(f"{doc.title}: {doc.content}" for doc in documents)
    prompt = (
        "Answer the question using only the context below. "
        "If the context does not contain the answer, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {payload.question}"
    )
    answer = llm_module.get_llm_provider().generate(prompt)

    return AskResponse(
        answer=answer,
        sources=[SourceRef(doc_id=str(doc.id), title=doc.title) for doc in documents],
    )
