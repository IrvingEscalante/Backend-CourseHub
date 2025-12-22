from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime


class PullRequest(Base):
    __tablename__ = 'pull_request'

    id_pull_request = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Info general
    title = Column(String(100))
    description_pull_request = Column(String(200))

    # Cursos involucrados
    id_course_source = Column(Integer, ForeignKey("course.id_course"), nullable=False)
    id_course_target = Column(Integer, ForeignKey("course.id_course"), nullable=False)

    # 🔥 Versiones involucradas (CLAVE)
    source_version_id = Column(
        Integer,
        ForeignKey("course_version.id_version"),
        nullable=False
    )
    target_version_id = Column(
        Integer,
        ForeignKey("course_version.id_version"),
        nullable=False
    )

    # Estado
    status_pull = Column(String(20), nullable=False, default="open")  # abierto / cerrado
    merge_status = Column(String(20), nullable=False, default="not merged")
    # not merged | merged | rejected

    # Usuarios
    id_user = Column(Integer, ForeignKey("user.id"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("user.id"), nullable=True)

    # Fechas
    date_created = Column(DateTime, default=datetime.now)
    date_resolved = Column(DateTime, nullable=True)

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
        foreign_keys=[source_version_id]
    )

    target_version = relationship(
        "CourseVersion",
        foreign_keys=[target_version_id]
    )

    # 🔥 Cambios del PR (diff congelado)
    changes = relationship(
        "PullRequestChange",
        back_populates="pull_request",
        cascade="all, delete-orphan"
    )
