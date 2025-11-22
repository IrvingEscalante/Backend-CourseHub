from pydantic import BaseModel
from datetime import datetime

class RecoverPasswordBase(BaseModel):
    id_user: int
    token: str
    date_expired: datetime
    used: bool = False

class RecoverPasswordCreate(RecoverPasswordBase):
    pass

class PasswordChange(BaseModel):
    token: str
    new_password: str

class RecoverPasswordRead(RecoverPasswordBase):
    id: int
    date_creation: datetime

    class Config:
        orm_mode = True
