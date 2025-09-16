from pydantic import BaseModel


class VerifyEmail(BaseModel):
    email: str
    code: str
