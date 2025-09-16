from fastapi_mail import FastMail, ConnectionConfig, MessageSchema
from app.core.config import settings


conf = ConnectionConfig(
    MAIL_USERNAME = settings.MAIL_USERNAME,
    MAIL_PASSWORD = settings.MAIL_PASSWORD,
    MAIL_FROM = settings.MAIL_USERNAME,
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)


async def send_verification_email(to_email: str, code: str):
    # message
    message = MessageSchema(
        subject="Verifica tu correo",
        recipients=[to_email],
        body=f"Tu código de verificación es: {code}",
        subtype="plain"  # o "html" si quieres HTML
    )
    # create instance of fastmail and send
    fm = FastMail(conf)
    await fm.send_message(message)
