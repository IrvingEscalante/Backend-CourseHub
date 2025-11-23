from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.content_publish import ContentCoursePublishResponse

# Schema para creación / input
class CoursePublishCreate(BaseModel):
    id_module: int
    name_publication: str
    description: str
    status_publish: bool

# Schema para respuesta / output
class CoursePublishResponse(BaseModel):
    id_course_publish: int
    id_module: int
    name_publication: str
    description: str
    date_created: datetime
    date_updated: Optional[datetime] = None
    status_publish: bool
    content:Optional[List[ContentCoursePublishResponse]] = None

    class Config:
        from_attributes = True
