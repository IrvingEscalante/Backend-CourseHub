from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime


class PullRequest(Base):
    __tablename__ = 'pull_request'

    id_pull_request = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(255), nullable=False)
    description_pull_request = Column(String(500), nullable=True)
    id_course_source = Column(Integer, ForeignKey("course.id_course"), nullable=False, index=True)
    id_course_target = Column(Integer, ForeignKey("course.id_course"), nullable=False, index=True)
    source_version_id = Column(Integer,ForeignKey("course_version.id_version"),nullable=False)
    target_version_id = Column(Integer,ForeignKey("course_version.id_version"),nullable=False)

    # Estado
    status_pull = Column(String(20), nullable=False, default="open", index=True)  # open | closed
    merge_status = Column(String(20), nullable=False, default="pending", index=True)
    # pending | merged | rejected

    # Usuarios
    id_user = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    reviewed_by = Column(Integer, ForeignKey("user.id"), nullable=True)

    # Fechas
    date_created = Column(DateTime, default=datetime.now, nullable=False)
    date_resolved = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)  # Cuando fue aprobado

    # --------------------
    # Relaciones
    # --------------------
    user = relationship(
        "User",
        foreign_keys=[id_user],
        back_populates="pull_requests_created"
    )

    reviewer = relationship(
        "User",
        foreign_keys=[reviewed_by],
        back_populates="pull_requests_reviewed"
    )

    course_source = relationship(
        "Course",
        foreign_keys=[id_course_source],
        back_populates="pull_requests_source"
    )

    course_target = relationship(
        "Course",
        foreign_keys=[id_course_target],
        back_populates="pull_requests_target"
    )

    source_version = relationship(
        "CourseVersion",
        foreign_keys=[source_version_id],
        backref="pr_as_source"
    )

    target_version = relationship(
        "CourseVersion",
        foreign_keys=[target_version_id],
        backref="pr_as_target"
    )

    # 🔥 Cambios del PR (diff congelado)
    changes = relationship(
        "PullRequestChange",
        back_populates="pull_request",
        cascade="all, delete-orphan"
    )

    # 📋 Cambios aplicados (audit trail)
    applied_changes = relationship(
        "AppliedChange",
        back_populates="pull_request",
        cascade="all, delete-orphan"
    )
    
    # Índices para búsquedas rápidas
    __table_args__ = (
        Index('idx_pr_status', 'status_pull', 'merge_status'),
        Index('idx_pr_user', 'id_user', 'date_created'),
        Index('idx_pr_courses', 'id_course_source', 'id_course_target'),
    )
