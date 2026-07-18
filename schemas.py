"""
Financial request endpoints: submission, viewing, and cancellation.
Approval/rejection actions live in routers/approvals.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import FinancialRequest, User, RoleEnum
from app.schemas import FinancialRequestCreate, FinancialRequestOut
from app.services import workflow

router = APIRouter(prefix="/requests", tags=["Financial Requests"])


@router.post("", response_model=FinancialRequestOut, status_code=status.HTTP_201_CREATED)
def submit_request(
    payload: FinancialRequestCreate, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fin_request = workflow.create_request_with_steps(
        db, requester=current_user, title=payload.title, description=payload.description,
        amount=payload.amount, currency=payload.currency, category=payload.category,
        ip_address=request.client.host if request.client else None,
    )
    return fin_request


@router.get("", response_model=list[FinancialRequestOut])
def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Employees see only their own requests. Managers/Finance/Admin also see
    requests currently awaiting their action (in addition to their own).
    """
    own_requests = db.query(FinancialRequest).filter(
        FinancialRequest.requester_id == current_user.id
    )

    if current_user.role == RoleEnum.EMPLOYEE:
        return own_requests.order_by(FinancialRequest.created_at.desc()).all()

    combined = {r.id: r for r in own_requests.all()}
    for r in list_pending_my_approval(db=db, current_user=current_user):
        combined[r.id] = r

    return sorted(combined.values(), key=lambda r: r.created_at, reverse=True)


@router.get("/pending-my-approval", response_model=list[FinancialRequestOut])
def list_pending_my_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Requests currently sitting at a step matching the caller's role."""
    from app.models import ApprovalStep, ApprovalStepStatus, RequestStatus

    results = []
    pending_requests = db.query(FinancialRequest).filter(
        FinancialRequest.status == RequestStatus.PENDING
    ).all()

    for fin_request in pending_requests:
        step = next(
            (s for s in fin_request.approval_steps if s.step_order == fin_request.current_step_order),
            None,
        )
        if step and step.status == ApprovalStepStatus.PENDING:
            if workflow.can_user_act_on_step(db, fin_request, step, current_user):
                results.append(fin_request)

    return results


@router.get("/{request_id}", response_model=FinancialRequestOut)
def get_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fin_request = db.query(FinancialRequest).filter(FinancialRequest.id == request_id).first()
    if not fin_request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    is_owner = fin_request.requester_id == current_user.id
    is_potential_approver = current_user.role != RoleEnum.EMPLOYEE
    if not (is_owner or is_potential_approver):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to view this request")

    return fin_request


@router.post("/{request_id}/cancel", response_model=FinancialRequestOut)
def cancel_request(
    request_id: str, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fin_request = db.query(FinancialRequest).filter(FinancialRequest.id == request_id).first()
    if not fin_request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    return workflow.cancel_request(
        db, fin_request, current_user,
        ip_address=request.client.host if request.client else None,
    )
