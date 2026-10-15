from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import settings
from src.infrastructure.services import email


@pytest.mark.asyncio
async def test_send_email_builds_smtp_message(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL", "user@example.com")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "smtp-password")
    monkeypatch.setattr(settings, "MAIL_PORT", 587)
    monkeypatch.setattr(settings, "MAIL_SERVER", "smtp.example.com")

    mail_client = MagicMock()
    mail_client.send_message = AsyncMock()
    fast_mail = MagicMock(return_value=mail_client)
    monkeypatch.setattr(email, "FastMail", fast_mail)

    await email.send_email(
        recipient="user@example.com",
        subject="Assunto",
        body="Conteúdo",
    )

    config = fast_mail.call_args.args[0]
    assert config.MAIL_SERVER == "smtp.example.com"
    assert config.MAIL_PORT == 587
    assert config.MAIL_USERNAME == "user@example.com"
    assert config.MAIL_FROM == "user@example.com"
    assert config.MAIL_STARTTLS is True
    assert config.MAIL_SSL_TLS is False

    mail_client.send_message.assert_awaited_once()
    message = mail_client.send_message.await_args.args[0]
    assert message.subject == "Assunto"
    assert [recipient.email for recipient in message.recipients] == ["user@example.com"]
    assert message.body == "Conteúdo"


@pytest.mark.asyncio
async def test_send_email_reports_missing_smtp_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL", "")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "")

    with pytest.raises(RuntimeError, match="EMAIL e EMAIL_PASSWORD"):
        await email.send_email("user@example.com", "Assunto", "Conteúdo")
