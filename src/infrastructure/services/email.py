from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from src.core.config import settings


async def send_email(recipient: str, subject: str, body: str) -> None:
    """Envia texto via SMTP com as credenciais configuradas para o Gmail."""
    if not settings.EMAIL or not settings.EMAIL_PASSWORD:
        raise RuntimeError(
            "Credenciais SMTP não configuradas. Defina EMAIL e EMAIL_PASSWORD."
        )

    connection_config = ConnectionConfig(
        MAIL_USERNAME=settings.EMAIL,
        MAIL_PASSWORD=settings.EMAIL_PASSWORD,
        MAIL_FROM=settings.EMAIL,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    message = MessageSchema(
        subject=subject,
        recipients=[recipient],
        body=body,
        subtype=MessageType.plain,
    )
    await FastMail(connection_config).send_message(message)
