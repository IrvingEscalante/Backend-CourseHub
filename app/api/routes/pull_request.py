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

@router.post("/create", response_model=PullRequestBasicOut)
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
    
    # 4️⃣ Obtener las últimas versiones de cada curso
    source_version = db.query(CourseVersion).filter(
        CourseVersion.id_course == source_course.id_course
    ).order_by(CourseVersion.version_number.desc()).first()
    
    target_version = db.query(CourseVersion).filter(
        CourseVersion.id_course == target_course.id_course
    ).order_by(CourseVersion.version_number.desc()).first()
    
    if not source_version or not target_version:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    
    # 5️⃣ Las versiones se obtienen directamente de los cursos
    
    try:
        # 6️⃣ Comparar snapshots
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
        
        return pull_request
    
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
    pull_request = db.query(PullRequest).options(
        joinedload(PullRequest.user),
        joinedload(PullRequest.reviewer)
    ).filter(PullRequest.id_course_target == id_course).all()
    if not pull_request:
        raise HTTPException(status_code=404, detail="No hay pull requests")
    return pull_request


@router.get("/my-pull-requests/{id_course}", response_model=List[PullRequestBasicOut])
def get_my_pull_requests(
    id_course:int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene todos los PRs que el usuario actual ha creado DESDE este curso
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    pull_requests = db.query(PullRequest).options(
        joinedload(PullRequest.user),
        joinedload(PullRequest.reviewer)
    ).filter(
        PullRequest.id_user == current_user.id,
        PullRequest.id_course_source == id_course
    ).all()
    
    return pull_requests


@router.patch("/{id_pull_request}/check-conflicts")
def check_pr_conflicts(
    id_pull_request: int,
    db: Session = Depends(get_db)
):
    """
    Verifica si hay cambios en el curso target desde que se creó el PR
    """
    pr = db.query(PullRequest).filter(
        PullRequest.id_pull_request == id_pull_request
    ).first()
    
    if not pr:
        raise HTTPException(404, "PR no encontrado")
    
    # Obtener versión actual del curso target
    latest_target_version = db.query(CourseVersion).filter(
        CourseVersion.id_course == pr.id_course_target
    ).order_by(CourseVersion.version_number.desc()).first()
    
    # Comparar con la versión que se usó para crear el PR
    if latest_target_version.id_version != pr.target_version_id:
        # Hay cambios en el target
        # Opción A: Recalcular diffs automáticamente
        source_version = db.query(CourseVersion).filter(
            CourseVersion.id_version == pr.source_version_id
        ).first()
        
        new_changes = compare_snapshots(
            latest_target_version.snapshot,
            source_version.snapshot
        )
        
        # Limpiar cambios antiguos
        db.query(PullRequestChange).filter(
            PullRequestChange.id_pull_request == id_pull_request
        ).delete()
        
        # Guardar nuevos cambios
        save_changes_to_db(db, id_pull_request, new_changes)
        
        # Actualizar versión del target
        pr.target_version_id = latest_target_version.id_version
        pr.has_conflicts = len([c for c in new_changes if c["action"] in ["DELETE", "UPDATE"]]) > 0
        
        db.commit()
        
        return {
            "message": "PR actualizado automáticamente",
            "has_conflicts": pr.has_conflicts,
            "changes_count": len(new_changes),
            "status": "updated"
        }
    
    return {
        "message": "No hay cambios en el curso target",
        "has_conflicts": False,
        "status": "current"
    }


@router.get("/{id_pull_request}", response_model=PullRequestBasicOut)
def get_pull_request_by_id(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los detalles de un Pull Request específico
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    pull_request = db.query(PullRequest).options(
        joinedload(PullRequest.user),
        joinedload(PullRequest.reviewer)
    ).filter(
        PullRequest.id_pull_request == id_pull_request
    ).first()
    
    if not pull_request:
        raise HTTPException(status_code=404, detail="Pull Request no encontrado")
    
    # Validar permisos: usuario debe ser propietario del curso target o creador del PR
    target_course = db.query(Course).filter(
        Course.id_course == pull_request.id_course_target
    ).first()
    
    if not target_course or (target_course.id_user != current_user.id and pull_request.id_user != current_user.id):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este PR")
    
    return pull_request


@router.get("/{id_pull_request}/changes")
def get_pull_request_changes(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todos los cambios asociados a un Pull Request
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    pull_request = db.query(PullRequest).filter(
        PullRequest.id_pull_request == id_pull_request
    ).first()
    
    if not pull_request:
        raise HTTPException(status_code=404, detail="Pull Request no encontrado")
    
    # Validar permisos
    target_course = db.query(Course).filter(
        Course.id_course == pull_request.id_course_target
    ).first()
    
    if not target_course or (target_course.id_user != current_user.id and pull_request.id_user != current_user.id):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver estos cambios")
    
    changes = db.query(PullRequestChange).filter(
        PullRequestChange.id_pull_request == id_pull_request
    ).order_by(PullRequestChange.date_created).all()
    
    return {
        "id_pull_request": id_pull_request,
        "changes": changes,
        "total": len(changes)
    }


@router.patch("/{id_pull_request}/accept")
def accept_pull_request(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acepta un Pull Request y aplica los cambios al curso target
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    pull_request = db.query(PullRequest).filter(
        PullRequest.id_pull_request == id_pull_request
    ).first()
    
    if not pull_request:
        raise HTTPException(status_code=404, detail="Pull Request no encontrado")
    
    # Validar que solo el propietario del curso target pueda aceptar
    target_course = db.query(Course).filter(
        Course.id_course == pull_request.id_course_target
    ).first()
    
    if not target_course or target_course.id_user != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el propietario del curso target puede aceptar este PR")
    
    if pull_request.status_pull != "open":
        raise HTTPException(status_code=400, detail=f"No se puede aceptar un PR con estado {pull_request.status_pull}")
    
    try:
        pull_request.status_pull = "closed"
        pull_request.merge_status = "merged"
        pull_request.reviewed_by = current_user.id
        pull_request.date_resolved = datetime.now()
        pull_request.approved_at = datetime.now()
        
        db.commit()
        
        return {
            "message": "Pull Request aceptado exitosamente",
            "status": "closed",
            "merge_status": "merged"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al aceptar el Pull Request: {str(e)}"
        )


@router.patch("/{id_pull_request}/reject")
def reject_pull_request(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rechaza un Pull Request
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    pull_request = db.query(PullRequest).filter(
        PullRequest.id_pull_request == id_pull_request
    ).first()
    
    if not pull_request:
        raise HTTPException(status_code=404, detail="Pull Request no encontrado")
    
    # Validar que solo el propietario del curso target pueda rechazar
    target_course = db.query(Course).filter(
        Course.id_course == pull_request.id_course_target
    ).first()
    
    if not target_course or target_course.id_user != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el propietario del curso target puede rechazar este PR")
    
    if pull_request.status_pull != "open":
        raise HTTPException(status_code=400, detail=f"No se puede rechazar un PR con estado {pull_request.status_pull}")
    
    try:
        pull_request.status_pull = "rejected"
        pull_request.merge_status = "rejected"
        pull_request.reviewed_by = current_user.id
        pull_request.date_resolved = datetime.now()
        
        db.commit()
        
        return {
            "message": "Pull Request rechazado",
            "status": "rejected",
            "merge_status": "rejected"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al rechazar el Pull Request: {str(e)}"
        )