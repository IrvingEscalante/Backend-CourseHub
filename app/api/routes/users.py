from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_user, hash_password
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.favorites_course import Favorites
from app.models.followers import Followers
from app.schemas.user_schema import UserPublicOut, UserPrivateOut, UserFollow, UserOut
from app.schemas.course_schema import AuthorResponse
from app.schemas.messageOut import MessageOut
from typing import Optional, Union
from app.schemas.verify_email import EmailIn
import secrets
from app.models.recover_password import RecoverPassword
from app.schemas.recover_password import PasswordChange
from datetime import datetime, timedelta
from app.services.email_services import send_recover_password

router = APIRouter()

@router.get("/profile", response_model=UserOut)
def profile(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(status_code=404, detail="El usuario no esta logueadoo")
    user_data = db.query(User).filter(User.id == current_user.id).first()
    if not user_data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_data:
        return user_data


@router.get("/user/{username}", response_model=Union[UserPrivateOut, UserPublicOut])
def get_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # IDs de mis favoritos
    my_favorite_ids = []
    if current_user:
        my_favorite_ids = [
            f.id_course for f in db.query(Favorites).filter(Favorites.id_user == current_user.id).all()
        ]

    # Cursos creados por el usuario
    user_courses = db.query(Course).filter(Course.id_user == user.id).all()
    courses_created = [
        {
            "id_course": c.id_course,
            "name_course": c.name_course,
            "description_course": c.description_course,
            "image": c.image,
            "id_user": c.id_user,
            "is_forked": c.is_forked,
            "id_author_user": c.id_author_user,
            "status_course": c.status_course,
            "date_created": c.date_created,
            "date_updated": c.date_updated,
            "is_my_favorite": c.id_course in my_favorite_ids,
            "author": AuthorResponse.model_validate(c.author) if c.author else None,
            "user": AuthorResponse.model_validate(c.user) if c.user else None
        }
        for c in user_courses
    ]

    # Cursos favoritos del usuario visitado
    favorite_ids = [f.id_course for f in db.query(Favorites).filter(Favorites.id_user == user.id).all()]
    favorite_courses = [
        {
            "id_course": c.id_course,
            "name_course": c.name_course,
            "description_course": c.description_course,
            "image": c.image,
            "id_user": c.id_user,
            "is_forked": c.is_forked,
            "id_author_user": c.id_author_user,
            "status_course": c.status_course,
            "date_created": c.date_created,
            "date_updated": c.date_updated,
            "is_my_favorite": c.id_course in my_favorite_ids,
            "author": AuthorResponse.model_validate(c.author) if c.author else None,
            "user": AuthorResponse.model_validate(c.user) if c.user else None
        }
        for c in db.query(Course).filter(Course.id_course.in_(favorite_ids)).all()
    ]
    followers_ids = [f.id_user for f in db.query(Followers).filter(Followers.id_user_follow == user.id).all()]
    following_ids = [f.id_user_follow for f in db.query(Followers).filter(Followers.id_user == user.id).all()]

    is_following = False
    is_mutual = False

    if current_user:
        # current_user sigue al usuario visitado
        is_following = db.query(Followers).filter(
            Followers.id_user == current_user.id,
            Followers.id_user_follow == user.id
        ).first() is not None

        # Relación mutua: ambos se siguen
        is_mutual = is_following and (current_user.id in following_ids)

    user_dict = user.__dict__.copy()
    user_dict["followers_count"] = len(followers_ids)
    user_dict["following_count"] = len(following_ids)
    user_dict["following"] = is_following
    user_dict["mutual"] = is_mutual
    user_dict["courses_create"] = courses_created
    user_dict["courses_favorites"] = favorite_courses


    if current_user and current_user.id == user.id:
        return UserPrivateOut(**user_dict)
    return UserPublicOut(**user_dict)


@router.post("/user/favorite/{id_course}", response_model=MessageOut)
def add_delete_favorites(id_course:int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    if not current_user:
        raise HTTPException(status_code=404, detail="No se encontro al usuario, no esta logueado")


    courses = db.query(Course).filter(Course.id_course == id_course).first()

    if not courses:
        raise HTTPException(status_code=404, detail="El curso no existe")

    exist_favorite = db.query(Favorites).filter(Favorites.id_user == current_user.id).filter(Favorites.id_course == id_course).first()

    if (exist_favorite):
        db.delete(exist_favorite)
        db.commit()
        return {"success":True, "message": "Se ha eliminado correctamente el curso"+ courses.name_course+" de favoritos"}

    new_favorite = Favorites(id_user = current_user.id, id_course = id_course)
    db.add(new_favorite)
    db.commit()
    db.refresh(new_favorite)

    return {"success":True, "message": "Se ha agregado correctamente el curso "+ courses.name_course+" a favoritos"}

@router.post("/user/follow_unfollow/{username}", response_model=UserFollow)
def follow_unfollow_user(username:str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=404, detail="No se puede seguir a un usuario sin una sesion iniciada")
    my_user = db.query(User).filter(User.id == current_user.id).first()
    if not my_user:
        raise HTTPException(status_code=404, detail="No se encontro al usuario")
    user_followed = db.query(User).filter(User.username == username).first()
    if not user_followed:
        raise HTTPException(status_code=404, detail="El usuario a seguir no existe")
    if my_user.id == user_followed.id:
        raise HTTPException(status_code=404, detail="No se puede seguir a uno mismo")

    exist_follow = db.query(Followers).filter(Followers.id_user == my_user.id).filter(Followers.id_user_follow == user_followed.id).first()
    if exist_follow:
        db.delete(exist_follow)
        db.commit()
        following = False
    else:
        new_follow = Followers(id_user=current_user.id, id_user_follow=user_followed.id)
        db.add(new_follow)
        db.commit()
        db.refresh(new_follow)
        following = True

    return UserFollow(
        username=user_followed.username,
        name=user_followed.name,
        lastname = user_followed.lastname,
        photo=user_followed.photo,
        following=following
    )

@router.post("/recover-password", response_model=MessageOut)
async def recover_password(email: EmailIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.email).first();
    print(email.email)
    if not user:
        raise HTTPException(status_code=404, detail="El usuario no esta registrado")
    token = secrets.token_hex(32)
    new_token = RecoverPassword(id_user = user.id, token=token, date_expired= datetime.now() + timedelta(minutes=10))
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    link = f"http://localhost:4200/change-password-recover?token={token}"
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