from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class CourseVersion(Base):
    __tablename__ = 'course_version'

    id_version = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_course = Column(Integer, ForeignKey("course.id_course"))
    version_number = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.now())
    created_by = Column(Integer)
    restored_from = Column(Integer)

    course_version = relationship("Course", back_populates="course")


