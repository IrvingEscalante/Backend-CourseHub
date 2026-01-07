from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from app.schemas.course_schema import CourseResponse

class UserOut(BaseModel):
    username:str
    name: str
    lastname:str
    email: str
    photo:str | None = None
    back_photo:str | None = None
    biography: str | None = None
    
class UserEdit(UserOut):
    pass

class UserOutFollow(BaseModel):
    username:str
    name: str
    lastname:str
    photo:str | None = None
    is_following:bool
    

class UserCreate(BaseModel):
    username: str
    name: str
    lastname: str
    email: EmailStr
    password: str
    

class UserPublicOut(BaseModel):
    username: str
    name: Optional[str] = None
    lastname: Optional[str] = None
    photo: Optional[str] = None
    back_photo: Optional[str] = None
    biography: Optional[str] = None
    date_joined: Optional[datetime] = None
    is_my_profile: bool = False
    followers_count : Optional[int] = None
    following_count : Optional[int] = None
    following : Optional[bool] = None
    mutual : Optional[bool] = None
    courses_create: List[CourseResponse] = [] 
    courses_favorites: List[CourseResponse] = []

    class Config:
        from_attributes = True

class UserPrivateOut(UserPublicOut):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True

class UserFollow(BaseModel):
    username:str
    name:str
    lastname:str
    photo:str | None = None
    following:bool

class AuthorResponse(BaseModel):
    id: int
    username: str
    name: str
    lastname: str
    photo: Optional[str] = None 
    biography: Optional[str] = None


    class Config:
        from_attributes = True  


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
