from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class CoursePublish(Base):
    __tablename__='course_publish'
    
    id_course_publish = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_module = Column(Integer, ForeignKey("module_course.id_module"))
    name_publication = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    date_created = Column(DateTime, default=datetime.now)
    date_updated = Column(DateTime, nullable=True)
    status_publish = Column(Boolean, nullable=False)

    module = relationship("ModuleCourse", back_populates="course_publish")
    content = relationship("ContentCoursePublish", back_populates="course_publish")

