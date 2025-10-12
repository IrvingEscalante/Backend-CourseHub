from sqlalchemy import Column, Integer, String, Boolean
from app.db.session import Base
from sqlalchemy.orm import relationship


class Theme(Base):
    __tablename__ = 'theme'

    id_theme = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name_theme = Column(String(50), nullable=False)
    status = Column(Boolean, default=True)

    courses = relationship("Course", back_populates="theme")

