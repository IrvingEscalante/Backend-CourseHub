from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_user
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_schema import UserPublicOut, UserPrivateOut
from typing import Optional, Union

router = APIRouter()

@router.get("/profile", response_model=UserPublicOut)
def profile(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    
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
    if current_user and current_user.id == user.id:
        return UserPrivateOut.model_validate(user)

    return UserPublicOut.model_validate(user)