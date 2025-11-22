from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class RecoverPassword(Base):
    __tablename__ = "recover_password"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_user = Column(Integer, ForeignKey("user.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    date_creation = Column(DateTime, default=datetime.now)
    date_expired = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    user = relationship("User", back_populates="recover_tokens")
