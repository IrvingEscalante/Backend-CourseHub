from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.schemas.user_schema import AuthorResponse

class PullRequestCreate(BaseModel):
    id_course_source: int
    id_course_target: int
    id_course_version_source: int | None = None  # Opcional - se usará la última versión
    id_course_version_target: int | None = None  # Opcional - se usará la última versión
    title: str | None = None
    description: str | None = None

class PullRequestBasicOut(BaseModel):
    id_pull_request: int
    title: Optional[str] = None
    description_pull_request: Optional[str] = None
    status_pull: str
    id_course_source: int
    id_course_target: int
    merge_status: str
    date_created: datetime
    date_resolved: Optional[datetime]
    user: AuthorResponse
    reviewer: Optional[AuthorResponse]
    class Config:
        from_attributes = True


"""
aqui por si lo ocupo:
class PullRequestOut(BaseModel):
    id_pull_request: int

    # Info general
    title: str
    description_pull_request: str

    # Estado
    status_pull: str
    merge_status: str

    # Fechas
    date_created: datetime
    date_resolved: Optional[datetime]

    # Usuarios
    user: UserBasic
    reviewer: Optional[UserBasic]

    # Cursos
    course_source: CourseBasic
    course_target: CourseBasic

    # Versiones involucradas
    source_version: CourseVersionBasic
    target_version: CourseVersionBasic

    # Cambios
    changes: List[PullRequestChangeOut] = []

    class Config:
        from_attributes = True

"""