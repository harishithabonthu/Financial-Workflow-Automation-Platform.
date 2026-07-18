"""
Database models: Users, Roles, Financial Requests, Approval Steps,
Audit Log entries, and Notifications.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class RoleEnum(str, enum.Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    FINANCE = "finance"
    ADMIN = "admin"


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalStepStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleEnum), nullable=False, default=RoleEnum.EMPLOYEE)
    is_active = Column(Boolean, default=True, nullable=False)
    manager_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    manager = relationship("User", remote_side=[id], backref="direct_reports")
    requests = relationship(
        "FinancialRequest", back_populates="requester",
        foreign_keys="FinancialRequest.requester_id"
    )


class FinancialRequest(Base):
    __tablename__ = "financial_requests"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    category = Column(String(100), nullable=True)

    requester_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(RequestStatus), nullable=False, default=RequestStatus.PENDING)

    current_step_order = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    requester = relationship("User", back_populates="requests", foreign_keys=[requester_id])
    approval_steps = relationship(
        "ApprovalStep", back_populates="request",
        order_by="ApprovalStep.step_order", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="request", cascade="all, delete-orphan")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    request_id = Column(UUID(as_uuid=False), ForeignKey("financial_requests.id"), nullable=False)
    step_order = Column(Integer, nullable=False)  # 1, 2, 3 ...
    required_role = Column(SAEnum(RoleEnum), nullable=False)
    approver_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(ApprovalStepStatus), nullable=False, default=ApprovalStepStatus.PENDING)
    comment = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("FinancialRequest", back_populates="approval_steps")
    approver = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    request_id = Column(UUID(as_uuid=False), ForeignKey("financial_requests.id"), nullable=True)
    actor_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g. "REQUEST_CREATED", "STEP_APPROVED"
    details = Column(Text, nullable=True)          # JSON-encoded extra context
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("FinancialRequest", back_populates="audit_logs")
    actor = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    request_id = Column(UUID(as_uuid=False), ForeignKey("financial_requests.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
