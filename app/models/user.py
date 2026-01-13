from sqlalchemy import Column, Integer, String,Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.course import Course
from datetime import datetime


class User(Base):
    __tablename__='user'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False)
    lastname = Column(String(50), nullable=False)
    email= Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    photo = Column(String(200), nullable=True)
    back_photo = Column(String(200), nullable=True)
    status = Column(Boolean, default=False)
    date_joined = Column(DateTime, default=datetime.now)
    biography = Column(String(100), nullable=True, default=None)

    verifications = relationship("EmailVerification", back_populates="user")
    courses = relationship("Course", foreign_keys=[Course.id_user], back_populates="user")
    authored_courses = relationship("Course", foreign_keys=[Course.id_author_user], back_populates="author")
    favorites = relationship("Favorites", back_populates="user")
    pull_requests_created = relationship("PullRequest", back_populates="user", foreign_keys='PullRequest.id_user')
    pull_requests_reviewed = relationship("PullRequest", back_populates="reviewer", foreign_keys='PullRequest.reviewed_by')
    rating = relationship("RatingCommentsCourse", back_populates="user_rating")
    notifications_sent = relationship("Notification", foreign_keys="[Notification.id_sender]", back_populates="sender")
    notifications_received = relationship("Notification", foreign_keys="[Notification.id_user]", back_populates="receiver")
    following = relationship("Followers", foreign_keys="[Followers.id_user]", back_populates="follower", cascade="all, delete-orphan")
    followers = relationship("Followers", foreign_keys="[Followers.id_user_follow]", back_populates="followed", cascade="all, delete-orphan")
    recover_tokens = relationship("RecoverPassword", back_populates="user")
    versions_created = relationship("CourseVersion", back_populates="user", foreign_keys='CourseVersion.created_by')


