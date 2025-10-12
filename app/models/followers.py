from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class Followers(Base):
    __tablename__ = 'followers'

    id_follow = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_user = Column(Integer)
    id_user_follow = Column(Integer)
    date_followed = Column(DateTime, default=datetime.now)