from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_user, hash_password
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.favorites_course import Favorites
from app.models.followers import Followers
from app.schemas.user_schema import UserPublicOut, UserPrivateOut, UserFollow, UserOut, UserOutFollow
from app.schemas.course_schema import AuthorResponse
from typing import List, Optional
from app.schemas.course_schema import CourseResponse
from app.schemas.verify_email import EmailIn
import secrets
from app.models.recover_password import RecoverPassword
from app.schemas.recover_password import PasswordChange
from datetime import datetime, timedelta
from app.services.email_services import send_recover_password


router = APIRouter()

@router.get("/following/{username}", response_model=List[UserOutFollow])
def get_all_following_by_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # usuarios que username sigue
    following_rel = db.query(Followers).filter(Followers.id_user == user.id).all()

    result = []
    for rel in following_rel:
        followed_user = db.query(User).filter(User.id == rel.id_user_follow).first()
        if not followed_user:
            continue

        if not current_user:
            is_following = False
        else:
            is_following = db.query(Followers).filter(
                Followers.id_user == current_user.id,
                Followers.id_user_follow == followed_user.id
            ).first() is not None

        result.append(
            UserOutFollow(
                id=followed_user.id,
                name=followed_user.name,
                lastname=followed_user.lastname,
                username=followed_user.username,
                photo=followed_user.photo,
                is_following=is_following
            )
        )

    return result

@router.get("/followers/{username}", response_model=List[UserOutFollow])
def get_all_followers_by_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    followers_rel = db.query(Followers).filter(Followers.id_user_follow == user.id).all()
    
    result = []
    for rel in followers_rel:
        follower_user = db.query(User).filter(User.id == rel.id_user).first()
        if not follower_user:
            continue
        
        # verificar si el usuario logueado sigue a ese seguidor
        if not current_user:
            is_following = False
        else:
            is_following = db.query(Followers).filter(
                Followers.id_user == current_user.id,
                Followers.id_user_follow == follower_user.id
            ).first() is not None

        result.append(
            UserOutFollow(
                id=follower_user.id,
                name=follower_user.name,
                lastname=follower_user.lastname,
                username=follower_user.username,
                photo=follower_user.photo,
                is_following=is_following
            )
        )
    print(result)
    return result
