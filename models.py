"""
Approval action endpoint. A manager/finance/admin user approves or
rejects the currently active step of a financial request.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import FinancialRequest, User
from app.schemas import ApprovalDecision, FinancialRequestOut
from app.services import workflow

router = APIRouter(prefix="/requests", tags=["Approvals"])


@router.post("/{request_id}/decision", response_model=FinancialRequestOut)
def decide(
    request_id: str, payload: ApprovalDecision, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fin_request = db.query(FinancialRequest).filter(FinancialRequest.id == request_id).first()
    if not fin_request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    return workflow.decide_step(
        db, fin_request, current_user,
        approve=payload.approve, comment=payload.comment,
        ip_address=request.client.host if request.client else None,
    )
