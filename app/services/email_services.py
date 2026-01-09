from fastapi_mail import FastMail, ConnectionConfig, MessageSchema
from app.core.config import settings
from datetime import datetime
from brevo_python import Configuration, ApiClient, TransactionalEmailsApi, SendSmtpEmail
import asyncio



# Configuration for FastMail (Commented - Using Brevo instead)
# conf = ConnectionConfig(
#     MAIL_USERNAME=settings.MAIL_USERNAME,
#     MAIL_PASSWORD=settings.MAIL_PASSWORD,
#     MAIL_FROM=settings.MAIL_USERNAME,
#     MAIL_PORT=465,
#     MAIL_SERVER="smtp.gmail.com",
#     MAIL_STARTTLS=False,
#     MAIL_SSL_TLS=True,
#     USE_CREDENTIALS=True,
#     VALIDATE_CERTS=True,
# )

# Brevo Configuration
brevo_conf = Configuration()
brevo_conf.api_key["api-key"] = settings.BREVO_API_KEY
brevo_api_client = ApiClient(brevo_conf)

async def send_verification_email(to_email: str, code: str, full_name_user, link_email_verification: str = ""):
    html_content = f"""
    <div style="font-family: Segoe UI, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px; background-color: #121C2D;">
        <h1 style="text-align:center; color:#fff">CourseHub</h1>
        <h2 style="color: #fff; text-align: center;">Verificación de Correo</h2>
        <p style="font-size: 16px; color: #fff;">
            Hola {full_name_user}, <br>
            Gracias por registrarte en <strong>CourseHub</strong>. Para completar tu registro, utiliza el siguiente código de verificación:
        </p>
        <div style="text-align: center; margin: 30px 0;">
            <span style="display: inline-block; font-size: 24px; letter-spacing: 5px; padding: 10px 20px; background-color: #1e3661; color: #fff; border-radius: 5px;">{code}</span>
        </div>
        <div>
  
            <a href="{ link_email_verification }">Entra a este enlace para ingresar tu código</a>

        </div>
        <p style="font-size: 14px; color: #fff;">
            Este código expirará en 10 minutos. <br>
            Si no solicitaste este código, puedes ignorar este correo.
        </p>
        <hr style="border: none; border-top: 2px solid #2D3A4F; margin: 20px 0;">
        <p style="font-size: 12px; color: #fff; text-align: center;">
            CourseHub &copy; {datetime.now().year}. Todos los derechos reservados.
        </p>
    </div>
    """

    send_smtp_email = SendSmtpEmail(
        to=[{"email": to_email, "name": full_name_user}],
        sender={"name": "CourseHub", "email": settings.BREVO_SENDER_EMAIL},
        subject="Verifica tu correo",
        html_content=html_content
    )

    try:
        api_instance = TransactionalEmailsApi(brevo_api_client)
        response = await asyncio.to_thread(api_instance.send_transac_email, send_smtp_email)
        return response
    except Exception as e:
        raise



async def send_recover_password(to_email: str, link_recover_password: str = ""):
    html_content = f"""
    <div style="font-family: Segoe UI, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px; background-color: #121C2D;">
        <h1 style="text-align:center; color:#fff">CourseHub</h1>
        <h2 style="color: #fff; text-align: center;">Recupera tu contraseña</h2>
        <div>
  
            <a href="{ link_recover_password }">Entra a este enlace para cambiar tu contraseña</a>

        </div>
        <p style="font-size: 14px; color: #fff;">
            Este código expirará en 10 minutos. <br>
            Si no solicitaste este código, puedes ignorar este correo.
        </p>
        <hr style="border: none; border-top: 2px solid #2D3A4F; margin: 20px 0;">
        <p style="font-size: 12px; color: #fff; text-align: center;">
            CourseHub &copy; {datetime.now().year}. Todos los derechos reservados.
        </p>
    </div>
    """

    send_smtp_email = SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"name": "CourseHub", "email": settings.BREVO_SENDER_EMAIL},
        subject="Recupera tu cuenta",
        html_content=html_content
    )

    try:
        api_instance = TransactionalEmailsApi(brevo_api_client)
        response = await asyncio.to_thread(api_instance.send_transac_email, send_smtp_email)
        return response
    except Exception as e:
        raise

