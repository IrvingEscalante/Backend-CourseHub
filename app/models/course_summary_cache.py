from sqlalchemy import Column, Integer, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class CourseSummaryCache(Base):
    __tablename__ = 'course_summary_cache'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id = Column(Integer, ForeignKey("course.id_course"), unique=True, nullable=False)
    summary = Column(Text, nullable=False)
    average_rating = Column(Float, nullable=True)
    comment_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    course = relationship("Course", backref="summary_cache")
