from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema para contenido individual en la creación
class ContentItemCreate(BaseModel):
    type_content: str  # 'image', 'video', 'note', 'file'
    content: str  # URL de imagen/archivo, URL de video, o texto de nota
    status: bool = True

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
