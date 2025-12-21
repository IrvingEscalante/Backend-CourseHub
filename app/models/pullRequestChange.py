from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.theme import Theme
from datetime import datetime

class PullRequestChange(Base):
    __tablename__ = 'pull_request_change'

    id_change = Column(Integer, primary_key=True, autoincrement=True)
    id_pull_request = Column(Integer,ForeignKey("pull_request.id_pull_request"),nullable=False)
    entity_type = Column(String(30))  # module | publication | content
    entity_id = Column(Integer, nullable=True)
    action = Column(String(10))  # ADD | UPDATE | DELETE
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    
    pull_request = relationship("PullRequest",back_populates="changes")
