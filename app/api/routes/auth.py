from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi.security import OAuth2PasswordRequestForm
from app.db.session import get_db
from app.models.user import User
from app.models.email_verification import EmailVerification  
import random
from app.schemas.user_schema import UserCreate, Token, UserPrivateOut
from app.schemas.verify_email import VerifyEmail
from app.utils.security import hash_password, verify_password, create_access_token
from datetime import datetime, timedelta
from app.services.email_services import send_verification_email
from app.schemas.messageOut import MessageOut
from app.schemas.verify_email import EmailIn
from app.utils.security import decrypt_email, encrypt_email
from app.schemas.user_schema import UserOut
from app.schemas.recover_password import PasswordChange
from app.core.config import settings


router = APIRouter()

def generate_code():
    return f"{random.randint(100000, 999999)}"


@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_email = db.query(User).filter(User.email == user.email).first()
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya está registrado"
        )

    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya está registrado"
        )

    new_user = User(username=user.username, name=user.name, lastname=user.lastname, email=user.email, hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    code = generate_code()
    verification = EmailVerification (
        user_id=new_user.id,
        code=code,
    )
    db.add(verification)
    db.commit()
    full_name = user.name + ' ' + user.lastname
    email_encrypted = encrypt_email(user.email)
    link = f"{settings.FRONTEND_URL}/verify-email?token={email_encrypted}"
    print("Este es el link: ", link)
    await send_verification_email(user.email, code, full_name, link)
    return {
        "user": new_user,
        "token_verification": email_encrypted
    }

# Iniciar sesión
@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(or_(User.email == form_data.username, User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.status:
        raise HTTPException(status_code=401, detail="La cuenta aun no ha sido verificada")
    access_token = create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/verify-email", response_model=MessageOut)
def verify_email(data: VerifyEmail, db: Session = Depends(get_db)):
    email_decrypted = decrypt_email(data.email)
    user = db.query(User).filter(User.email == email_decrypted).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.status:
        raise HTTPException(status_code=404, detail="Tu correo ya esta verificado")
    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user.id,
            EmailVerification.code == data.code,
            EmailVerification.is_used == False,
            EmailVerification.expires_at > datetime.now()
        )
        .first()
    )

    if not verification:
        raise HTTPException(status_code=404, detail="Codigo invalido o expirado")
    
    verification.is_used = True
    user.status = True
    db.commit()

    return {
        "success": True,
        "message": "Codigo verificado correctamente"}



@router.post("/resend-code", response_model=MessageOut)
async def resend_code(data:EmailIn, db: Session = Depends(get_db)):
    email_decrypted = decrypt_email(data.email)
    user = db.query(User).filter(User.email == email_decrypted).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.status:
        raise HTTPException(status_code=404, detail="Tu correo ya esta verificado")

    # Obtener el último código enviado para este usuario
    last_verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.user_id == user.id)
        .order_by(EmailVerification.created_at.desc())
        .first()
    )
    
    # Verificar si pasó suficiente tiempo desde el último envío
    if last_verification and last_verification.last_code_sent_at:
        elapsed_seconds = (datetime.now() - last_verification.last_code_sent_at).total_seconds()
        if elapsed_seconds < 30:
            raise HTTPException(status_code=404, detail="Espera 30 segundos antes de pedir otro código")
    
    # Invalidar códigos antiguos
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.is_used == False
    ).update({EmailVerification.is_used: True})

    # Generar un nuevo código y agregar una nueva fila
    code = generate_code()
    new_verification = EmailVerification(
        user_id=user.id,
        code=code,
        expires_at=datetime.now() + timedelta(minutes=10),
        last_code_sent_at = datetime.now()
    )
    db.add(new_verification)
    db.commit()

    full_name = user.name + ' ' + user.lastname
    # Enviar correo con el nuevo código
    await send_verification_email(email_decrypted, code, full_name)

    return {
        "success": True,
        "message": "Se ha reenviado el codigo de confirmación"}



@router.post("/recover-password", response_model=MessageOut)
async def recover_password(email: EmailIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.email).first()
    print(email.email)
    if not user:
        raise HTTPException(status_code=404, detail="El usuario no esta registrado")
    token = secrets.token_hex(32)
    new_token = RecoverPassword(id_user = user.id, token=token, date_expired= datetime.now() + timedelta(minutes=10))
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    link = f"{settings.FRONTEND_URL}/change-password-recover?token={token}"
    await send_recover_password(email.email, link)
    return {
        "success": True,
        "message": "Se ha enviado el correo electronico"}

@router.post("/change-password")
async def change_password(data: PasswordChange, db: Session = Depends(get_db)):
    recover = db.query(RecoverPassword).filter(RecoverPassword.token == data.token).first()

    if not recover:
        raise HTTPException(status_code=404, detail="Token no válido")

    if recover.used:
        raise HTTPException(status_code=400, detail="Token ya fue usado")

    if recover.date_expired < datetime.now():
        raise HTTPException(status_code=400, detail="Token expirado")

    user = db.query(User).filter(User.id == recover.id_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.hashed_password = hash_password(data.new_password)
    recover.used = True  # marcar token como usado
    db.commit()

    return {"success": True, "message": "Contraseña cambiada correctamente"}

