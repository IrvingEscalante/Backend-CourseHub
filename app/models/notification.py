#Pendiente
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class Notification(Base):
    __tablename__ = 'notification'

    id_notification = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_user = Column(Integer, ForeignKey("user.id"))
    id_sender = Column(Integer, ForeignKey("user.id"))
    type = Column(String(50))
    entity_type = Column(String(50))
    message = Column(String(255))
    link = Column(String(255))
    is_read = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    read_at = Column(DateTime, nullable=True)

    sender = relationship("User", foreign_keys=[id_sender])
    receiver = relationship("User", foreign_keys=[id_user])
