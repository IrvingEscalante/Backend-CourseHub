from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from app.schemas.course_schema import CourseResponse

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
    biography: Optional[str] = None
    date_joined: Optional[datetime] = None
    courses: List[CourseResponse] = [] 

    class Config:
        from_attributes = True

class UserPrivateOut(UserPublicOut):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True



class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
