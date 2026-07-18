"""
Audit trail endpoints. Admins can view the full system audit log,
optionally filtered by request; any user can view the audit trail for
requests they own.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import AuditLog, FinancialRequest, User, RoleEnum
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[AuditLogOut])
def list_all_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.ADMIN)),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()


@router.get("/request/{request_id}", response_model=list[AuditLogOut])
def get_request_audit_trail(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fin_request = db.query(FinancialRequest).filter(FinancialRequest.id == request_id).first()
    if not fin_request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    is_owner = fin_request.requester_id == current_user.id
    if not (is_owner or current_user.role in (RoleEnum.ADMIN, RoleEnum.FINANCE, RoleEnum.MANAGER)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    return db.query(AuditLog).filter(AuditLog.request_id == request_id).order_by(
        AuditLog.created_at.asc()
    ).all()
