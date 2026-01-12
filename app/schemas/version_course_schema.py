from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class CourseVersionSnapshot(BaseModel):
    """Esquema para el snapshot JSON almacenado en la BD"""
    image: str
    id_user: int
    modules: Optional[List[Dict[str, Any]]] = None
    id_theme: int
    id_course: int
    is_forked: bool
    name_course: str
    uuid_course: str
    date_created: str
    date_updated: Optional[str] = None
    status_course: bool
    id_author_user: int
    description_course: str

    class Config:
        from_attributes = True

class CourseVersionResponse(BaseModel):
    """Esquema para retornar una versión del curso"""
    id_version: int
    id_course: int
    version_number: int
    snapshot: CourseVersionSnapshot
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True

class CourseVersionListResponse(BaseModel):
    """Esquema para listar versiones (resumido)"""
    id_version: int
    id_course: int
    version_number: int
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True
