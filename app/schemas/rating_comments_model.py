from pydantic import BaseModel
from datetime import datetime

class RatingCommentsCourseResponse(BaseModel):
    id_ratings_comments: int
    id_course: int
    comment_detail: str
    id_user: int
    rating: int 
    status: bool
    date_created: datetime

    class Config:
        from_attributes = True
