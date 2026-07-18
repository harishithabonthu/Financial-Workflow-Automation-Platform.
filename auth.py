"""
Notification service. Creates in-app notification records and,
if configured, sends an email via SMTP. Email sending is best-effort
and never blocks or fails the primary workflow transaction.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Notification, User

logger = logging.getLogger("workflow.notifications")
settings = get_settings()


def notify_user(db: Session, user: User, message: str, request_id: str = None) -> Notification:
    notification = Notification(
        user_id=user.id,
        message=message,
        request_id=request_id,
    )
    db.add(notification)
    db.flush()

    if settings.NOTIFICATIONS_ENABLED:
        _send_email_best_effort(user.email, "Financial Workflow Notification", message)

    return notification


def _send_email_best_effort(to_email: str, subject: str, body: str) -> None:
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - notifications must never break the workflow
        logger.warning("Email notification failed for %s: %s", to_email, exc)
