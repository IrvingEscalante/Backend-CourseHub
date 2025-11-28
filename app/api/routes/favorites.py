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
from typing import List, Optional
from app.schemas.course_schema import CourseResponse
from app.schemas.verify_email import EmailIn
import secrets
from app.models.recover_password import RecoverPassword
from app.schemas.recover_password import PasswordChange
from datetime import datetime, timedelta
from app.services.email_services import send_recover_password


router = APIRouter()

@router.get("/{username}", response_model=List[CourseResponse])
def favorites_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="No se encontró el usuario")

    # Obtener favoritos del usuario consultado
    favorites = (
        db.query(Favorites)
        .filter(Favorites.id_user == user.id)
        .all()
    )

    courses = []

    for fav in favorites:
        course = (
            db.query(Course)
            .filter(Course.id_course == fav.id_course)
            .first()
        )
        if not course:
            continue

        # Convertir el curso al schema
        course_schema = CourseResponse.model_validate(course)

        # Calcular si ES favorito para el usuario que está logueado
        if current_user:
            exists = (
                db.query(Favorites)
                .filter(
                    Favorites.id_user == current_user.id,
                    Favorites.id_course == course.id_course
                )
                .first()
            )
            course_schema.is_my_favorite = exists is not None
        else:
            course_schema.is_my_favorite = False

        courses.append(course_schema)

    return courses


@router.post("/add_delete/{id_course}", response_model=MessageOut)
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
