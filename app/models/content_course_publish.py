from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class ContentCoursePublish(Base):
    __tablename__ = 'content_course_publish'

    id_content_course_publish = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_course_publish = Column(Integer, ForeignKey("course_publish.id_course_publish"))
    content = Column(String(500), nullable=False)
    status = Column(Boolean, nullable=False)
    type_content = Column(String(45))
    date_created = Column(DateTime, default=datetime.now)
    
    course_publish = relationship("CoursePublish", back_populates="content")