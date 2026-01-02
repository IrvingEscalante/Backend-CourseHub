from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File, Request
from sqlalchemy import or_
from app.utils.security import get_current_user
from sqlalchemy import func
import json
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.theme import Theme
from app.models.module_course import ModuleCourse
from app.models.course_publish import CoursePublish
from app.models.version_course import CourseVersion
from app.models.content_course_publish import ContentCoursePublish
from app.models.favorites_course import Favorites
from app.models.pull_request import PullRequest
from app.models.pullRequestChange import PullRequestChange
from typing import List, Optional, Dict
from app.services.user_services import get_favorite_ids
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local, compress_image
from app.services.version_services import compare_snapshots, save_changes_to_db
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload, CourseBase
from app.schemas.pull_request_schema import PullRequestCreate, PullRequestBasicOut
import asyncio
from PIL import Image
import io
import os
from datetime import datetime

router = APIRouter()

@router.post("/create")
def create_pull_request(
    pr_payload: PullRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuevo Pull Request comparando dos versiones de cursos
    y guardando los cambios en la BD
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Debes estar logueado para crear un PR")
    
    # 1️⃣ Validar que los cursos existan
    source_course = db.query(Course).filter(
        Course.id_course == pr_payload.id_course_source
    ).first()
    target_course = db.query(Course).filter(
        Course.id_course == pr_payload.id_course_target
    ).first()
    
    if not source_course or not target_course:
        raise HTTPException(status_code=404, detail="Curso source o target no encontrado")
    
    # 2️⃣ Validar que el usuario sea el propietario del curso source
    print(source_course.id_user)
    print(current_user.id)
    if source_course.id_user != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo el propietario del curso source puede crear un PR"
        )
    
    # 3️⃣ Validar que el usuario NO sea el propietario del curso target
    if target_course.id_user == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="No puedes hacer PR a tu propio curso"
        )
    
    # 4️⃣ Validar que el curso target sea la versión original (no un fork)
    if target_course.is_forked:
        raise HTTPException(
            status_code=400,
            detail="No puedes hacer PR a un curso que es un fork"
        )
    
    # 5️⃣ Obtener versiones
    source_version = db.query(CourseVersion).filter(
        CourseVersion.id_version == pr_payload.id_course_version_source
    ).first()
    target_version = db.query(CourseVersion).filter(
        CourseVersion.id_version == pr_payload.id_course_version_target
    ).first()
    
    if not source_version or not target_version:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    
    # 6️⃣ Validar que las versiones pertenezcan a sus respectivos cursos
    if source_version.id_course != source_course.id_course:
        raise HTTPException(
            status_code=400,
            detail="La versión source no pertenece al curso source"
        )
    
    if target_version.id_course != target_course.id_course:
        raise HTTPException(
            status_code=400,
            detail="La versión target no pertenece al curso target"
        )
    
    try:
        # 7️⃣ Comparar snapshots
        changes = compare_snapshots(
            target_version.snapshot,  # versión anterior (destino)
            source_version.snapshot   # versión propuesta (fuente)
        )
        
        pull_request = PullRequest(
            title=pr_payload.title or f"PR: {source_course.name_course} → {target_course.name_course}",
            description_pull_request=pr_payload.description,
            id_course_source=source_course.id_course,
            id_course_target=target_course.id_course,
            source_version_id=source_version.id_version,
            target_version_id=target_version.id_version,
            id_user=current_user.id,
            status_pull="open",
            merge_status="pending"
        )
        db.add(pull_request)
        db.flush()
        
        save_changes_to_db(db, pull_request.id_pull_request, changes)
        
        db.commit()
        
        return {
            "message": "Pull Request creado exitosamente",
            "pull_request_id": pull_request.id_pull_request,
            "title": pull_request.title,
            "status": pull_request.status_pull,
            "merge_status": pull_request.merge_status,
            "changes_count": len(changes),
            "created_at": pull_request.date_created.isoformat()
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear el Pull Request: {str(e)}"
        )

@router.get("/get_pull_request/{id_course}", response_model=List[PullRequestBasicOut])
def get_pull_request(id_course:int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=404, detail="No estas logueado para acceder a los pull requets")
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="No existe un curso con este id")
    user_owner_course = db.query(User).filter(User.id == course.id_user).first()
    if user_owner_course.id != current_user.id:
        raise HTTPException(status_code=404, detail="No tienes permiso para ver estos pull request")
    pull_request = db.query(PullRequest).filter(PullRequest.id_course_target == id_course)
    if not pull_request:
        raise HTTPException(status_code=404, detail="No hay pull requests")
    return pull_request

