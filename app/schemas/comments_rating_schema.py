from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.schemas.user_schema import UserOut

class RatingCommentsCourseBase(BaseModel):
    id_course: int
    comment_detail: str
    rating: int = Field(..., ge=1, le=5)

class RatingCommentsCourseCreate(RatingCommentsCourseBase):
    pass

class RatingCommentsCourseUpdate(BaseModel):
    comment_detail: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)

class RatingCommentsCourseResponse(RatingCommentsCourseBase):
    id_ratings_comments: int
    date_created: datetime
    user_rating: Optional[UserOut] = None
    status:bool

    class Config:
        from_attributes = True
