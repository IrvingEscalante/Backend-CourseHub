from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema para creación / input
class ContentCoursePublishCreate(BaseModel):
    id_course_publish: int
    content: str
    status: bool


class ContentCoursePublishResponse(BaseModel):
    id_content_course_publish: int
    id_course_publish: int
    content: str
    status: bool
    type_content:str

    class Config:
        from_attributes = True
