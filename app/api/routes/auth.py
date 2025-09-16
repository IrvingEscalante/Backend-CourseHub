from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.db.session import get_db
from app.models.auth.user import User
from app.models.auth.email_verification import EmailVerification  
import random
from app.schemas.user_schema import UserCreate, UserOut, Token
from app.schemas.verify_email import VerifyEmail
from app.utils.security import hash_password, verify_password, create_access_token
from datetime import datetime, timedelta
from app.services.email_services import send_verification_email
from app.models.generic_response_model import ResponseModel

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def generate_code():
    return f"{random.randint(100000, 999999)}"

@router.post("/register", response_model=ResponseModel[UserOut])
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_email = db.query(User).filter(User.email == user.email).first()
    if db_email:
        return ResponseModel(success=False, message="El correo ya está registrado")

    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        return ResponseModel(success=False, message="El usuario ya está registrado")

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
    #  Enviar correo
    await send_verification_email(user.email, code)
    return ResponseModel(success=True, data=new_user)

# Iniciar sesión
@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.status:
        raise HTTPException(status_code=401, detail="La cuenta aun no ha sido verificada")
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/verify-email", response_model=ResponseModel[None])
def verify_email(data: VerifyEmail, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return ResponseModel(success = False, message = "Usuario no encontrado")
    
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
        return ResponseModel(success = False, message = "Código invalido o expirado")
    
    verification.is_used = True
    user.status = True
    db.commit()

    return ResponseModel(success = True, message = "Correo verificado correctamente")


@router.post("/resend-code")
async def resend_code(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return ResponseModel(success=False, message="Usuario no encontrado")
    
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
        if elapsed_seconds < 300:  # 5 minutos
            return ResponseModel(success=False, message="Espera 5 minutos antes de pedir otro código")
    
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
        last_code_sent_at=datetime.now()
    )
    db.add(new_verification)
    db.commit()

    # Enviar correo con el nuevo código
    await send_verification_email(user.email, code)

    return ResponseModel(success=True, message="Se ha enviado un nuevo código")
