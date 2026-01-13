from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.rating_comments_model import RatingCommentsCourseResponse


class AuthorResponse(BaseModel):
    id: int
    username: str
    name: str
    email: str
    lastname: str
    photo: Optional[str] = None 
    biography: Optional[str] = None


    class Config:
        from_attributes = True  


class CourseBase(BaseModel):
    id_course:int
    name_course: str
    description_course: str
    image: str
    is_forked: bool
    id_theme: int
    status_course: Optional[bool] = True


class CourseCreate(CourseBase):
    pass

class CourseResponse(BaseModel):
    id_course: int
    id_course_parent: Optional[int] = None
    name_course: str
    description_course: str
    image: Optional[str]
    id_user: int
    is_forked: bool
    id_author_user: Optional[int]
    id_theme: Optional[int]
    status_course: bool
    is_my_favorite: bool = False
    is_my_course:bool =False
    is_favorite: bool = False
    date_created: datetime
    date_updated: Optional[datetime]

    avg_rating: Optional[float] = None
    ratings_count: Optional[int] = None
    ratings_breakdown: Optional[dict] = None
    author: Optional[AuthorResponse] = None
    user: Optional[AuthorResponse] = None

    num_videos: Optional[int] = 0
    num_files: Optional[int] = 0
    num_embed: Optional[int] = 0
    num_notes: Optional[int] = 0
    num_images: Optional[int] = 0

    class Config:
        from_attributes = True  

class CourseUpdate(BaseModel):
    name_course: Optional[str] = None
    description_course: Optional[str] = None
    image: Optional[str] = None
    id_user: Optional[int] = None
    is_forked: Optional[bool] = None
    id_author_user: Optional[int] = None
    id_theme: Optional[int] = None
    status_course: Optional[bool] = None
    date_updated: Optional[datetime] = None


class CourseInDBBase(CourseBase):
    id_course: int
    date_created: datetime
    date_updated: Optional[datetime] = None

    class Config:
        from_attributes = True  # antes orm_mode=True


class Course(CourseInDBBase):
    pass


class CourseInDB(CourseInDBBase):
    pass

# schemas/course.py
from pydantic import BaseModel
from typing import List, Optional


class ResourcePayload(BaseModel):
    type: str   # image, pdf, pptx, video, note
    value: Optional[str] = None
    fileKey: Optional[str] = None
    fileName: Optional[str] = None


class PublicationPayload(BaseModel):
    title: str
    description: str
    resources: List[ResourcePayload]


class ModulePayload(BaseModel):
    title: str
    description: str
    publications: List[PublicationPayload]


class CoursePayload(BaseModel):
    title: str
    topic: Optional[int]
    description: Optional[str]

class ResourceResponse(BaseModel):
    id_content_course_publish: int
    id_course_publish: int
    content: str
    status: bool
    type_content: str

    class Config:
        from_attributes = True

class PublicationResponse(BaseModel):
    id_course_publish: int
    id_module: int
    name_publication: str
    description: Optional[str] = None
    date_created: Optional[datetime] = None
    date_updated: Optional[datetime] = None
    status_publish: bool
    content: List[ResourceResponse] = []

    class Config:
        from_attributes = True

class ModuleResponse(BaseModel):
    id_module: int
    id_course: int
    name_module: str
    description_module: Optional[str] = None
    status_module: bool
    order_index: int
    date_created: Optional[datetime] = None
    course_publish: List[PublicationResponse] = []

    class Config:
        from_attributes = True


class CourseFullResponse(BaseModel):
    id_course:int
    name_course: str
    description_course: str
    image: str
    is_forked: bool
    id_theme: int
    status_course: Optional[bool] = True
    modules: List[ModuleResponse]

    class Config:
        from_attributes = True
