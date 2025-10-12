from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class RatingCommentsCourse(Base):
    __tablename__ = 'rating_comments_course'

    id_ratings_comments = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_course = Column(Integer, ForeignKey("course.id_course"))
    comment_detail = Column(String(200), nullable=False)
    id_user = Column(Integer, ForeignKey("user.id"))
    rating = Column(Integer, nullable=False)
    status = Column(Boolean, nullable=False)
    date_created = Column(DateTime, default=datetime.now)

    course_rating = relationship("Course", back_populates="rating")
    user_rating = relationship("User", back_populates="rating")
    
