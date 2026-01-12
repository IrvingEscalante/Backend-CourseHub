from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.version_course import CourseVersion
from app.models.course import Course
from app.models.user import User
from app.utils.security import get_current_user
from typing import List
from app.schemas.version_course_schema import CourseVersionResponse, CourseVersionListResponse

router = APIRouter()

@router.get("/course/{id_course}/versions", response_model=List[CourseVersionListResponse])
def get_versions_by_course(
    id_course: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todas las versiones de un curso.
    Retorna lista de versiones ordenadas por version_number descendente (más nuevas primero).
    """
    # Verificar que el curso existe
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    # Obtener versiones ordenadas descendentemente
    versions = db.query(CourseVersion)\
        .filter(CourseVersion.id_course == id_course)\
        .order_by(CourseVersion.version_number.desc())\
        .all()
    
    if not versions:
        raise HTTPException(status_code=404, detail="No hay versiones para este curso")
    
    return versions


@router.get("/course/{id_course}/versions/{id_version}", response_model=CourseVersionResponse)
def get_version(
    id_course: int,
    id_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene una versión específica de un curso.
    Retorna todos los datos del snapshot junto con metadatos de la versión.
    """
    # Buscar la versión
    version = db.query(CourseVersion)\
        .filter(
            CourseVersion.id_version == id_version,
            CourseVersion.id_course == id_course
        )\
        .first()
    
    if not version:
        raise HTTPException(
            status_code=404, 
            detail=f"Versión {id_version} no encontrada para el curso {id_course}"
        )
    
    return version


@router.get("/course/{id_course}/versions/latest", response_model=CourseVersionResponse)
def get_latest_version(
    id_course: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene la versión más reciente de un curso.
    """
    # Verificar que el curso existe
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    # Obtener la versión con el mayor version_number
    latest_version = db.query(CourseVersion)\
        .filter(CourseVersion.id_course == id_course)\
        .order_by(CourseVersion.version_number.desc())\
        .first()
    
    if not latest_version:
        raise HTTPException(status_code=404, detail="No hay versiones disponibles para este curso")
    
    return latest_version
