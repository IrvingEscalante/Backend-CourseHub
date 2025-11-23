from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema para creación / input
class ContentCoursePublishCreate(BaseModel):
    id_course_publish: int
    content: str
    status: bool

# Schema para respuesta / output
class ContentCoursePublishResponse(BaseModel):
    id_content_course_publish: int
    id_course_publish: int
    content: str
    status: bool

    class Config:
        from_attributes = True
