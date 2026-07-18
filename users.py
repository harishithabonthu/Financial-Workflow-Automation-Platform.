"""
Core workflow engine.

Responsible for:
  - Determining which approval levels a request needs, based on amount.
  - Creating the ApprovalStep chain when a request is submitted.
  - Advancing the request through steps as approvals/rejections happen.
  - Resolving the correct approver for the current step (e.g. the
    requester's direct manager for a MANAGER-level step).
"""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    FinancialRequest, ApprovalStep, ApprovalStepStatus,
    RequestStatus, RoleEnum, User,
)
from app.services import audit, notifications

settings = get_settings()


def required_roles_for_amount(amount: float) -> List[RoleEnum]:
    """
    Determine the ordered chain of approval roles required for a given
    request amount. Higher amounts require more approval levels.
    """
    if amount < settings.APPROVAL_THRESHOLD_LEVEL_1:
        return [RoleEnum.MANAGER]
    if amount < settings.APPROVAL_THRESHOLD_LEVEL_2:
        return [RoleEnum.MANAGER, RoleEnum.FINANCE]
    return [RoleEnum.MANAGER, RoleEnum.FINANCE, RoleEnum.ADMIN]


def create_request_with_steps(
    db: Session, requester: User, title: str, description: str,
    amount: float, currency: str, category: str, ip_address: str = None,
) -> FinancialRequest:
    roles_chain = required_roles_for_amount(amount)

    fin_request = FinancialRequest(
        title=title,
        description=description,
        amount=amount,
        currency=currency,
        category=category,
        requester_id=requester.id,
        status=RequestStatus.PENDING,
        current_step_order=1,
    )
    db.add(fin_request)
    db.flush()

    for order, role in enumerate(roles_chain, start=1):
        step = ApprovalStep(
            request_id=fin_request.id,
            step_order=order,
            required_role=role,
            status=ApprovalStepStatus.PENDING,
        )
        db.add(step)

    db.flush()

    audit.log_action(
        db, action="REQUEST_CREATED", actor_id=requester.id, request_id=fin_request.id,
        details={"amount": amount, "currency": currency, "approval_chain": [r.value for r in roles_chain]},
        ip_address=ip_address,
    )

    _notify_next_approvers(db, fin_request)

    db.commit()
    db.refresh(fin_request)
    return fin_request


def _resolve_approver_candidates(db: Session, fin_request: FinancialRequest, role: RoleEnum) -> List[User]:
    """
    Find users eligible to act on a given step. For MANAGER steps we
    prefer the requester's direct manager; otherwise any active user
    holding the required role can approve (typical for FINANCE/ADMIN pools).
    """
    if role == RoleEnum.MANAGER and fin_request.requester.manager_id:
        manager = db.query(User).filter(
            User.id == fin_request.requester.manager_id, User.is_active == True  # noqa: E712
        ).first()
        if manager:
            return [manager]

    return db.query(User).filter(User.role == role, User.is_active == True).all()  # noqa: E712


def _notify_next_approvers(db: Session, fin_request: FinancialRequest) -> None:
    current_step = next(
        (s for s in fin_request.approval_steps if s.step_order == fin_request.current_step_order),
        None,
    )
    if current_step is None:
        return

    candidates = _resolve_approver_candidates(db, fin_request, current_step.required_role)
    for candidate in candidates:
        notifications.notify_user(
            db, candidate,
            message=f"Approval needed: '{fin_request.title}' (${fin_request.amount:.2f}) "
                    f"from {fin_request.requester.full_name}",
            request_id=fin_request.id,
        )


def get_current_step(fin_request: FinancialRequest) -> ApprovalStep:
    step = next(
        (s for s in fin_request.approval_steps if s.step_order == fin_request.current_step_order),
        None,
    )
    if step is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request has no active approval step")
    return step


def can_user_act_on_step(db: Session, fin_request: FinancialRequest, step: ApprovalStep, user: User) -> bool:
    if user.role != step.required_role:
        return False
    candidates = _resolve_approver_candidates(db, fin_request, step.required_role)
    return any(c.id == user.id for c in candidates)


def decide_step(
    db: Session, fin_request: FinancialRequest, user: User,
    approve: bool, comment: str = None, ip_address: str = None,
) -> FinancialRequest:
    if fin_request.status != RequestStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request is not pending approval")

    step = get_current_step(fin_request)

    if not can_user_act_on_step(db, fin_request, step, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to act on this step")

    from datetime import datetime
    step.approver_id = user.id
    step.comment = comment
    step.decided_at = datetime.utcnow()

    if approve:
        step.status = ApprovalStepStatus.APPROVED
        audit.log_action(
            db, action="STEP_APPROVED", actor_id=user.id, request_id=fin_request.id,
            details={"step_order": step.step_order, "role": step.required_role.value, "comment": comment},
            ip_address=ip_address,
        )

        remaining_steps = [s for s in fin_request.approval_steps if s.step_order > step.step_order]
        if remaining_steps:
            fin_request.current_step_order = min(s.step_order for s in remaining_steps)
            _notify_next_approvers(db, fin_request)
        else:
            fin_request.status = RequestStatus.APPROVED
            audit.log_action(
                db, action="REQUEST_APPROVED", actor_id=user.id, request_id=fin_request.id,
                ip_address=ip_address,
            )
            notifications.notify_user(
                db, fin_request.requester,
                message=f"Your request '{fin_request.title}' was fully approved.",
                request_id=fin_request.id,
            )
    else:
        step.status = ApprovalStepStatus.REJECTED
        fin_request.status = RequestStatus.REJECTED

        audit.log_action(
            db, action="REQUEST_REJECTED", actor_id=user.id, request_id=fin_request.id,
            details={"step_order": step.step_order, "role": step.required_role.value, "comment": comment},
            ip_address=ip_address,
        )
        notifications.notify_user(
            db, fin_request.requester,
            message=f"Your request '{fin_request.title}' was rejected at the "
                    f"{step.required_role.value} approval step.",
            request_id=fin_request.id,
        )

    db.commit()
    db.refresh(fin_request)
    return fin_request


def cancel_request(db: Session, fin_request: FinancialRequest, user: User, ip_address: str = None) -> FinancialRequest:
    if fin_request.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the requester can cancel this request")
    if fin_request.status != RequestStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending requests can be cancelled")

    fin_request.status = RequestStatus.CANCELLED
    audit.log_action(
        db, action="REQUEST_CANCELLED", actor_id=user.id, request_id=fin_request.id, ip_address=ip_address,
    )
    db.commit()
    db.refresh(fin_request)
    return fin_request
