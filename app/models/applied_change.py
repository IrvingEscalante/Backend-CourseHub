from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class AppliedChange(Base):
    __tablename__ = 'applied_change'

    id_applied = Column(Integer, primary_key=True, autoincrement=True)
    id_pull_request = Column(Integer, ForeignKey("pull_request.id_pull_request"), nullable=False, index=True)
    id_change = Column(Integer, ForeignKey("pull_request_change.id_change"), nullable=False)
    
    # Información del elemento afectado
    entity_type = Column(String(30), nullable=False)  # module | publication | content
    entity_uuid = Column(String(36), nullable=False)
    entity_id = Column(Integer, nullable=True)  # ID asignado después de crear
    
    # Estado de la aplicación
    status = Column(String(20), nullable=False, default="pending")  # pending | success | failed | skipped
    error_message = Column(Text, nullable=True)
    
    # Auditoría
    applied_at = Column(DateTime, nullable=True)
    applied_by = Column(Integer, ForeignKey("user.id"), nullable=True)
    
    # Relaciones
    pull_request = relationship("PullRequest", back_populates="applied_changes")
    user = relationship("User")
