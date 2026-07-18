"""
Audit logging service. Every meaningful state change in the system
(request creation, approval, rejection, user management) is recorded
here to build a complete, queryable audit trail.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        actor_id=actor_id,
        request_id=request_id,
        details=json.dumps(details) if details is not None else None,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()  # get entry.id without committing the outer transaction
    return entry
