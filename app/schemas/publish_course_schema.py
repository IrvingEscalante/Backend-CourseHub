from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.schemas.content_publish import ContentCoursePublishResponse, ContentItemCreate

"""
 id_course_publish = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_module = Column(Integer, ForeignKey("module_course.id_module"))
    name_publication = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    date_created = Column(DateTime, default=datetime.now)
    date_updated = Column(DateTime, nullable=True)
    status_publish = Column(Boolean, nullable=False)
"""

class CreatePublicationRequest(BaseModel):
    name_publication: str
    description: str

class PublishCourseResponse(BaseModel):
    id_course_publish:int
    id_module:int
    name_publication:str
    description:str
    date_created:datetime
    date_updated:Optional[datetime]
    status_publish:bool
    content:List[ContentCoursePublishResponse] = []

    class Config:
        from_attributes = True