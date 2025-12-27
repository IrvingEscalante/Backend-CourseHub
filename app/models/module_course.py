from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime


class ModuleCourse(Base):
    __tablename__='module_course'

    id_module = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_course = Column(Integer, ForeignKey("course.id_course"))
    name_module = Column(String(50), nullable=False)
    description_module = Column(String(100), nullable=False)
    status_module = Column(Boolean, nullable=False)
    order_index = Column(Integer, nullable=False)
    date_created = Column(DateTime, default=datetime.now)

    course = relationship("Course", back_populates="modules")
    course_publish = relationship("CoursePublish", back_populates="module")
