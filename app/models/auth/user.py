from sqlalchemy import Column, Integer, String,Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base


class User(Base):
    __tablename__='user'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False)
    lastname = Column(String(50), nullable=False)
    email= Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    photo = Column(String(200))
    status = Column(Boolean, default=False)

    verifications = relationship("EmailVerification", back_populates="user")

