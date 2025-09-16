from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    name: str
    lastname: str
    email: EmailStr
    password: str
    

class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        orm_mode=True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
