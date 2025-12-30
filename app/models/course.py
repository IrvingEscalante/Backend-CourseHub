from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.session import Base
import uuid
from app.models.theme import Theme
from datetime import datetime

class Course(Base):
    __tablename__='course'

    id_course = Column(Integer, primary_key=True, autoincrement=True, index=True)
    uuid_course = Column(String(36), default=lambda: str(uuid.uuid4()), nullable=False)
    base_version = Column(Integer, ForeignKey("course_version.id_version"))
    id_course_parent = Column(Integer, ForeignKey("course.id_course"), nullable=True)
    name_course = Column(String(100), nullable=False)
    description_course = Column(Text, nullable=False)
    image = Column(String(200), nullable=False)
    id_user = Column(Integer, ForeignKey("user.id"))
    is_forked = Column(Boolean, nullable=False)
    id_author_user = Column(Integer, ForeignKey("user.id"))
    id_theme = Column(Integer, ForeignKey("theme.id_theme"))
    status_course = Column(Boolean, default=True)
    date_created = Column(DateTime, default=datetime.now)
    date_updated = Column(DateTime, default=None)

    user = relationship("User", foreign_keys=[id_user], back_populates="courses")
    author = relationship("User", foreign_keys=[id_author_user], back_populates="authored_courses")
    theme = relationship("Theme", back_populates="courses")
    modules = relationship("ModuleCourse", back_populates="course")
    favorites = relationship("Favorites", back_populates="course_favorites")
    pull_requests_source = relationship("PullRequest", back_populates="course_source", foreign_keys='PullRequest.id_course_source')
    pull_requests_target = relationship("PullRequest", back_populates="course_target", foreign_keys='PullRequest.id_course_target')
    rating = relationship("RatingCommentsCourse", back_populates="course_rating")
    parent_course = relationship("Course",remote_side=[id_course],backref="forks")
    versions = relationship("CourseVersion",back_populates="course",foreign_keys="CourseVersion.id_course",cascade="all, delete-orphan")

    base_course_version = relationship(
        "CourseVersion",
        foreign_keys=[base_version]
    )
