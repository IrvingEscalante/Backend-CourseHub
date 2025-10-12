from pydantic import BaseModel


class VerifyEmail(BaseModel):
    email: str
    code: str

class EmailIn(BaseModel):
    email: str