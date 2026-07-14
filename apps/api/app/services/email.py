"""Email behind a provider interface (ARCHITECTURE.md): SMTP → Mailpit locally,
SES/Resend in production by swapping the provider, not the callers."""

import smtplib
from email.message import EmailMessage
from typing import Protocol

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("email")


class EmailProvider(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpEmailProvider:
    def send(self, to: str, subject: str, body: str) -> None:
        settings = get_settings()
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(msg)
        logger.info("email_sent", to=to, subject=subject)


def get_email_provider() -> EmailProvider:
    return SmtpEmailProvider()
