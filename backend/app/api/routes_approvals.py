import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models import ApprovalRequest, User
from app.tools.registry import TOOLS

router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    decision: str  # "approve" | "deny"


def _require_admin(user: User) -> None:
    if str(user.role) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


@router.get("")
def list_approvals(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_admin(current_user)
    approvals = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.tenant_id == current_user.tenant_id)
        .all()
    )
    return [
        {
            "id": str(a.id),
            "tool_name": a.tool_name,
            "tool_args": a.tool_args,
            "risk_level": a.risk_level,
            "status": a.status,
        }
        for a in approvals
    ]


@router.post("/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    payload: DecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)

    try:
        approval = db.query(ApprovalRequest).filter(
            ApprovalRequest.id == uuid.UUID(approval_id)
        ).first()
    except ValueError:
        approval = None

    if approval is None or str(approval.tenant_id) != str(current_user.tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if approval.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already decided")

    if payload.decision == "approve":
        requester = db.get(User, approval.requested_by_user_id)
        tool_fn = TOOLS[approval.tool_name]
        tool_fn(**approval.tool_args, user=requester, db=db)
        approval.status = "approved"
    else:
        approval.status = "denied"

    approval.decided_by_user_id = current_user.id
    approval.decided_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": approval.status}
