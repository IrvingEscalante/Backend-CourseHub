from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.db.session import Base

class EmailVerification(Base):
    __tablename__ = "email_verification"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, default=lambda: datetime.now() + timedelta(minutes=30))
    last_code_sent_at = Column(DateTime, default=datetime.now)


    user = relationship("User", back_populates="verifications")
