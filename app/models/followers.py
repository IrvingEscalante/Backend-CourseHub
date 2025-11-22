from sqlalchemy import Column, Integer, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class Followers(Base):
    __tablename__ = 'followers'

    
    id_user = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    id_user_follow = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    date_followed = Column(DateTime, default=datetime.now)

    __table_args__ = (
        # Evita que un usuario se siga a sí mismo
        CheckConstraint('id_user != id_user_follow', name='no_self_follow'),
    )

    follower = relationship("User", foreign_keys=[id_user], back_populates="following")           # Quien sigue
    followed = relationship("User", foreign_keys=[id_user_follow], back_populates="followers")    #