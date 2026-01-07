from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from app.utils.security import get_current_user, hash_password
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.favorites_course import Favorites
from app.models.followers import Followers
from app.schemas.user_schema import UserPublicOut, UserPrivateOut, UserFollow, UserOut, UserEdit
from app.schemas.course_schema import AuthorResponse
from app.utils.security import verify_password
from typing import Optional, Union
from app.schemas.verify_email import EmailIn
import secrets
from app.models.recover_password import RecoverPassword
from app.schemas.recover_password import PasswordChange
from app.services.user_services import get_courses_created, get_favorite_courses, get_follow_data, get_user_by_username, get_favorite_ids
from datetime import datetime, timedelta
from app.services.email_services import send_recover_password
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local
import asyncio
from PIL import Image

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

    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    follow_data = get_follow_data(db, user, current_user)
    favorite_ids = set(get_favorite_ids(db, current_user))

    courses_created = get_courses_created(db, user, favorite_ids) 
    favorites = get_favorite_courses(db, user, current_user, favorite_ids)

    isMyProfile = current_user and current_user.id == user.id

    user_dict = user.__dict__.copy()
    user_dict.update(follow_data)
    user_dict["courses_create"] = courses_created
    user_dict["courses_favorites"] = favorites
    user_dict["is_my_profile"] = isMyProfile

    if current_user and current_user.id == user.id:
        return UserPrivateOut(**user_dict)

    return UserPublicOut(**user_dict)



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


@router.patch("/edit-profile", response_model=UserOut)
async def edit_profile(
    name: str | None = Form(None),
    lastname: str | None = Form(None),
    email: str | None = Form(None),
    username: str | None = Form(None),
    biography: str | None = Form(None),
    currentPassword: str | None = Form(None),
    newPassword: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    back_photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == current_user.id).first()

    if not user:
        raise HTTPException(status_code=404, detail="El usuario no existe")

    # ---------------------------------
    # 1. Actualizar SOLO lo que venga
    # ---------------------------------
    if name is not None and name != user.name:
        user.name = name

    if lastname is not None and lastname != user.lastname:
        user.lastname = lastname

    if email is not None and email != user.email:
        email_exists = (db.query(User).filter(User.email == email,User.id != user.id).first())
        if email_exists:
            raise HTTPException(
                status_code=400,
                detail="El email ya está en uso"
            )
        user.email = email

    if username is not None and username != user.username:
        username_exists = (
            db.query(User)
            .filter(
                User.username == username,
                User.id != user.id
            )
            .first()
        )

        if username_exists:
            raise HTTPException(
                status_code=400,
                detail="El nombre de usuario ya está en uso"
            )

        user.username = username


    if biography is not None and biography != user.biography:
        user.biography = biography

    if newPassword:
        if not currentPassword:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar la contraseña actual"
            )

        if not verify_password(currentPassword, user.hashed_password):
            raise HTTPException(
                status_code=400,
                detail="La contraseña actual es incorrecta"
            )

        user.hashed_password = hash_password(newPassword)

    # ---------------------------------
    # 3. Avatar (Cloudinary)
    # ---------------------------------
    if avatar:
        file_bytes = await avatar.read()

        avatar_url = await upload_to_cloudinary(
            file_bytes,
            "profile_images_presets"
        )

        user.photo = avatar_url
    
    if back_photo:
        file_bytes = await back_photo.read()
        back_photo_url = await upload_to_cloudinary(file_bytes, "profile_images_presets")
        user.back_photo = back_photo_url



    # ---------------------------------
    # 4. Guardar cambios
    # ---------------------------------
    db.commit()
    db.refresh(user)

    return user