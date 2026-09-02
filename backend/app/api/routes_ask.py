from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.graph import build_agent_graph
from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.schemas.ask import AskRequest, AskResponse, SourceRef

router = APIRouter(tags=["ask"])

_agent = build_agent_graph()


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    result = _agent.invoke(
        {
            "question": payload.question,
            "user": current_user,
            "db": db,
            "documents": [],
            "answer": "",
        }
    )

    return AskResponse(
        answer=result["answer"],
        sources=[
            SourceRef(doc_id=str(doc.id), title=doc.title) for doc in result["documents"]
        ],
    )
