from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class Favorites(Base):

    __tablename__ = 'favorites_course'

    id_favorite = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_user = Column(Integer, ForeignKey("user.id"))
    id_course = Column(Integer, ForeignKey("course.id_course"))

    user = relationship("User", back_populates="favorites")
    course = relationship("Course", back_populates="favorites")