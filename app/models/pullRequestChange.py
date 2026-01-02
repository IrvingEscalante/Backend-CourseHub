from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.theme import Theme
from datetime import datetime

class PullRequestChange(Base):
    __tablename__ = 'pull_request_change'

    id_change = Column(Integer, primary_key=True, autoincrement=True)
    id_pull_request = Column(Integer, ForeignKey("pull_request.id_pull_request"), nullable=False, index=True)
    
    # Tipo de entidad y su identificación
    entity_type = Column(String(30), nullable=False)  # course | module | publication | content
    entity_id = Column(Integer, nullable=True)  # ID de la entidad
    entity_uuid = Column(String(36), nullable=True)  # UUID para rastreo cross-version
    
    # Acción realizada
    action = Column(String(10), nullable=False)  # ADD | UPDATE | DELETE
    reason = Column(String(30), nullable=True)  # "removed" | "status_disabled"
    
    # Para cambios complejos (objetos completos)
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    
    # Para cambios simples de campos individuales
    field = Column(String(50), nullable=True)  # Nombre del campo (ej: name_course, description_module)
    old_value = Column(Text, nullable=True)  # Valor anterior como texto/JSON
    new_value = Column(Text, nullable=True)  # Valor nuevo como texto/JSON
    
    # Auditoría
    date_created = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relación
    pull_request = relationship("PullRequest", back_populates="changes")
    
    # Índices para búsquedas rápidas
    __table_args__ = (
        Index('idx_pr_entity', 'id_pull_request', 'entity_type'),
        Index('idx_entity_uuid', 'entity_uuid'),
        Index('idx_action', 'action'),
    )
