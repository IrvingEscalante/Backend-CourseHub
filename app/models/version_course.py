from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class CourseVersion(Base):
    __tablename__ = 'course_version'

    id_version = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_course = Column(Integer, ForeignKey("course.id_course"))
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now())
    created_by = Column(Integer, ForeignKey("user.id"))

    course = relationship(
        "Course",
        back_populates="versions",
        foreign_keys=[id_course]
    )
    user = relationship(
        "User",
        back_populates="versions_created",
        foreign_keys=[created_by]
    )


