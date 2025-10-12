from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class PullRequest(Base):
    __tablename__ = 'pull_request'

    id_pull_request = Column(Integer, primary_key=True, autoincrement=True, index=True)
    detail = Column(String(100))
    description_pull_request = Column(String(200))
    id_course_source = Column(Integer, ForeignKey("course.id_course"))
    status_pull = Column(Boolean, nullable=False)
    id_user = Column(Integer, ForeignKey("user.id"))
    id_course_target = Column(Integer,ForeignKey("course.id_course"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("user.id"))
    date_created = Column(DateTime, default=datetime.now())
    date_resolved = Column(DateTime)
    merge_status = Column(String(20), nullable=False, default="not merged")

    user = relationship("User", back_populates="pull_requests_created", foreign_keys=[id_user])
    reviewer = relationship("User", back_populates="pull_requests_reviewed", foreign_keys=[reviewed_by])
    course_source = relationship("Course", foreign_keys=[id_course_source], back_populates="pull_requests_source")
    course_target = relationship("Course", foreign_keys=[id_course_target], back_populates="pull_requests_target")
