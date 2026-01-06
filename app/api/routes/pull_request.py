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
from app.models.applied_change import AppliedChange
from typing import List, Optional, Dict
from app.services.user_services import get_favorite_ids
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local
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
    
    # 5️⃣ Serializar el estado actual de ambos cursos (no usar snapshot guardado)
    from app.services.version_services import serialize_course_to_snapshot
    
    try:
        source_snapshot = serialize_course_to_snapshot(db, source_course.id_course)
        target_snapshot = serialize_course_to_snapshot(db, target_course.id_course)
        
        # 6️⃣ Comparar snapshots actuales
        changes = compare_snapshots(
            target_snapshot,  # estado actual del destino
            source_snapshot   # estado actual de la fuente
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
    Obtiene todos los cambios asociados a un Pull Request con información del contexto
    (nombre del padre: módulo para publicaciones, publicación para contenidos, etc)
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
    
    # Enriquecer cambios con información del padre
    enriched_changes = []
    for change in changes:
        change_dict = {
            "id_change": change.id_change,
            "id_pull_request": change.id_pull_request,
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_uuid": change.entity_uuid,
            "action": change.action,
            "reason": change.reason,
            "old_data": change.old_data,
            "new_data": change.new_data,
            "field": change.field,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "date_created": change.date_created,
            # Información del contexto
            "parent_info": None
        }
        
        # Agregar información del padre según el tipo de entidad
        if change.entity_type == "content":
            # Obtener la publicación padre
            if change.new_data and "id_course_publish" in change.new_data:
                pub_id = change.new_data["id_course_publish"]
            elif change.old_data and "id_course_publish" in change.old_data:
                pub_id = change.old_data["id_course_publish"]
            else:
                pub_id = None
            
            if pub_id:
                publication = db.query(CoursePublish).filter(
                    CoursePublish.id_course_publish == pub_id
                ).first()
                if publication:
                    change_dict["parent_info"] = {
                        "parent_type": "publication",
                        "parent_id": publication.id_course_publish,
                        "parent_name": publication.name_publication
                    }
        
        elif change.entity_type == "publication":
            # Obtener el módulo padre
            if change.new_data and "id_module" in change.new_data:
                module_id = change.new_data["id_module"]
            elif change.old_data and "id_module" in change.old_data:
                module_id = change.old_data["id_module"]
            else:
                module_id = None
            
            if module_id:
                module = db.query(ModuleCourse).filter(
                    ModuleCourse.id_module == module_id
                ).first()
                if module:
                    change_dict["parent_info"] = {
                        "parent_type": "module",
                        "parent_id": module.id_module,
                        "parent_name": module.name_module
                    }
        
        elif change.entity_type == "module":
            # El padre del módulo es el curso, pero generalmente no es necesario mostrar
            # Se puede agregar si es necesario
            pass
        
        enriched_changes.append(change_dict)
    
    return {
        "id_pull_request": id_pull_request,
        "changes": enriched_changes,
        "total": len(enriched_changes)
    }


@router.post("/{id_pull_request}/validate-merge")
def validate_merge(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Valida si todos los cambios del PR pueden aplicarse correctamente
    sin realizar cambios en la BD. Retorna errores o advertencias.
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
        raise HTTPException(status_code=403, detail="No tienes permiso para validar este PR")
    
    changes = db.query(PullRequestChange).filter(
        PullRequestChange.id_pull_request == id_pull_request
    ).all()
    
    validation_results = []
    has_errors = False
    
    for change in changes:
        result = {
            "id_change": change.id_change,
            "entity_type": change.entity_type,
            "entity_uuid": change.entity_uuid,
            "action": change.action,
            "status": "valid",
            "errors": [],
            "warnings": []
        }
        
        try:
            # Validar según el tipo de acción
            if change.action == "ADD":
                validation_error = _validate_add_change(db, pull_request, change)
                if validation_error:
                    result["status"] = "error"
                    result["errors"].append(validation_error)
                    has_errors = True
                    
            elif change.action == "UPDATE":
                validation_error = _validate_update_change(db, pull_request, change)
                if validation_error:
                    result["status"] = "error"
                    result["errors"].append(validation_error)
                    has_errors = True
                    
            elif change.action == "DELETE":
                validation_error = _validate_delete_change(db, pull_request, change)
                if validation_error:
                    result["status"] = "error"
                    result["errors"].append(validation_error)
                    has_errors = True
            else:
                result["status"] = "error"
                result["errors"].append(f"Acción desconocida: {change.action}")
                has_errors = True
                
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(str(e))
            has_errors = True
        
        validation_results.append(result)
    
    return {
        "id_pull_request": id_pull_request,
        "can_merge": not has_errors,
        "total_changes": len(changes),
        "valid_changes": len([r for r in validation_results if r["status"] == "valid"]),
        "invalid_changes": len([r for r in validation_results if r["status"] == "error"]),
        "validations": validation_results
    }


@router.patch("/{id_pull_request}/accept")
def accept_pull_request(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acepta un Pull Request y aplica los cambios al curso target
    con registro completo de auditoría
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
        # Obtener todos los cambios asociados al PR
        changes = db.query(PullRequestChange).filter(
            PullRequestChange.id_pull_request == id_pull_request
        ).all()
        
        applied_count = 0
        failed_count = 0
        
        # Aplicar cada cambio según su tipo de acción
        for change in changes:
            applied_record = AppliedChange(
                id_pull_request=id_pull_request,
                id_change=change.id_change,
                entity_type=change.entity_type,
                entity_uuid=change.entity_uuid,
                status="pending"
            )
            
            try:
                if change.action == "ADD":
                    success, entity_id, error = _apply_add_change(db, pull_request, change)
                elif change.action == "UPDATE":
                    success, entity_id, error = _apply_update_change(db, pull_request, change)
                elif change.action == "DELETE":
                    success, entity_id, error = _apply_delete_change(db, pull_request, change)
                else:
                    success, entity_id, error = False, None, f"Acción desconocida: {change.action}"
                
                if success:
                    applied_record.status = "success"
                    applied_record.entity_id = entity_id
                    applied_record.applied_at = datetime.now()
                    applied_record.applied_by = current_user.id
                    applied_count += 1
                else:
                    applied_record.status = "failed"
                    applied_record.error_message = error
                    failed_count += 1
                    
            except Exception as e:
                applied_record.status = "failed"
                applied_record.error_message = str(e)
                failed_count += 1
            
            db.add(applied_record)
        
        # Si hay fallos, hacer rollback
        if failed_count > 0:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Error aplicando cambios: {failed_count} cambio(s) fallaron. Transacción revertida."
            )
        
        # Actualizar estado del PR
        pull_request.status_pull = "closed"
        pull_request.merge_status = "merged"
        pull_request.reviewed_by = current_user.id
        pull_request.date_resolved = datetime.now()
        pull_request.approved_at = datetime.now()
        
        db.commit()
        
        return {
            "message": "Pull Request aceptado exitosamente",
            "status": "closed",
            "merge_status": "merged",
            "changes_applied": applied_count,
            "changes_failed": failed_count
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al aceptar el Pull Request: {str(e)}"
        )


def _apply_add_change(db: Session, pull_request: PullRequest, change: PullRequestChange):
    """
    Aplica un cambio de tipo ADD: crea un nuevo elemento con los datos propuestos
    Retorna (success: bool, entity_id: int|None, error: str|None)
    """
    entity_type = change.entity_type
    new_data = change.new_data
    
    try:
        if entity_type == "module":
            # Crear nuevo módulo en el curso target
            new_module = ModuleCourse(
                uuid_module=change.entity_uuid,
                id_course=pull_request.id_course_target,
                name_module=new_data.get("name_module"),
                description_module=new_data.get("description_module"),
                status_module=new_data.get("status_module", True),
                order_index=new_data.get("order_index", 0)
            )
            db.add(new_module)
            db.flush()
            return True, new_module.id_module, None
            
        elif entity_type == "publication":
            # El new_data contiene id_module del source, pero necesitamos el UUID del módulo
            # para encontrarlo en el target
            source_module_id = new_data.get("id_module")
            
            # Buscar el UUID del módulo en el source
            source_module = db.query(ModuleCourse).filter(
                ModuleCourse.id_module == source_module_id
            ).first()
            
            if not source_module:
                return False, None, f"No se encontró módulo source con id {source_module_id}"
            
            # Encontrar el módulo correspondiente en el target usando UUID
            target_module = db.query(ModuleCourse).filter(
                ModuleCourse.uuid_module == source_module.uuid_module,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not target_module:
                return False, None, f"No se encontró módulo en target con UUID {source_module.uuid_module}"
            
            # Crear nueva publicación en el módulo target
            new_publication = CoursePublish(
                uuid_publish=change.entity_uuid,
                id_module=target_module.id_module,
                name_publication=new_data.get("name_publication"),
                description=new_data.get("description"),
                status_publish=new_data.get("status_publish", True)
            )
            db.add(new_publication)
            db.flush()
            return True, new_publication.id_course_publish, None
            
        elif entity_type == "content":
            # El new_data contiene id_course_publish del source, pero necesitamos el UUID
            # para encontrarlo en el target
            source_pub_id = new_data.get("id_course_publish")
            
            # Buscar la publicación en el source
            source_pub = db.query(CoursePublish).filter(
                CoursePublish.id_course_publish == source_pub_id
            ).first()
            
            if not source_pub:
                return False, None, f"No se encontró publicación source con id {source_pub_id}"
            
            # Encontrar la publicación correspondiente en el target usando UUID
            target_pub = db.query(CoursePublish).join(ModuleCourse).filter(
                CoursePublish.uuid_publish == source_pub.uuid_publish,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not target_pub:
                return False, None, f"No se encontró publicación en target con UUID {source_pub.uuid_publish}"
            
            # Crear nuevo contenido en la publicación target
            new_content = ContentCoursePublish(
                uuid_content=change.entity_uuid,
                id_course_publish=target_pub.id_course_publish,
                content=new_data.get("content"),
                status=new_data.get("status", True),
                type_content=new_data.get("type_content")
            )
            db.add(new_content)
            db.flush()
            return True, new_content.id_content_course_publish, None
        
        elif entity_type == "course":
            # Los cambios del curso se ignoran en la aplicación (no se modifican datos del curso principal)
            return True, pull_request.id_course_target, None
            
    except Exception as e:
        return False, None, str(e)


def _apply_update_change(db: Session, pull_request: PullRequest, change: PullRequestChange):
    """
    Aplica un cambio de tipo UPDATE: actualiza los datos del elemento existente
    Retorna (success: bool, entity_id: int|None, error: str|None)
    """
    entity_type = change.entity_type
    new_data = change.new_data
    
    try:
        if entity_type == "module":
            # Buscar módulo por UUID en el curso target
            module = db.query(ModuleCourse).filter(
                ModuleCourse.uuid_module == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not module:
                return False, None, f"Módulo con UUID {change.entity_uuid} no encontrado en el curso target"
            
            if "name_module" in new_data:
                module.name_module = new_data["name_module"]
            if "description_module" in new_data:
                module.description_module = new_data["description_module"]
            if "status_module" in new_data:
                module.status_module = new_data["status_module"]
            if "order_index" in new_data:
                module.order_index = new_data["order_index"]
            
            return True, module.id_module, None
            
        elif entity_type == "publication":
            # Buscar publicación por UUID SOLO en módulos del curso target
            publication = db.query(CoursePublish).join(
                ModuleCourse
            ).filter(
                CoursePublish.uuid_publish == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not publication:
                return False, None, f"Publicación con UUID {change.entity_uuid} no encontrada en el curso target"
            
            if "name_publication" in new_data:
                publication.name_publication = new_data["name_publication"]
            if "description" in new_data:
                publication.description = new_data["description"]
            if "status_publish" in new_data:
                publication.status_publish = new_data["status_publish"]
            publication.date_updated = datetime.now()
            
            return True, publication.id_course_publish, None
            
        elif entity_type == "content":
            # Buscar contenido por UUID SOLO en publicaciones del curso target
            content = db.query(ContentCoursePublish).join(
                CoursePublish
            ).join(
                ModuleCourse
            ).filter(
                ContentCoursePublish.uuid_content == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not content:
                return False, None, f"Contenido con UUID {change.entity_uuid} no encontrado en el curso target"
            
            if "content" in new_data:
                content.content = new_data["content"]
            if "status" in new_data:
                content.status = new_data["status"]
            if "type_content" in new_data:
                content.type_content = new_data["type_content"]
            
            return True, content.id_content_course_publish, None
        
        elif entity_type == "course":
            # Los cambios del curso se ignoran en la aplicación
            return True, pull_request.id_course_target, None
            
    except Exception as e:
        return False, None, str(e)


def _apply_delete_change(db: Session, pull_request: PullRequest, change: PullRequestChange):
    """
    Aplica un cambio de tipo DELETE: cambia el status a 0 (inactivo)
    Retorna (success: bool, entity_id: int|None, error: str|None)
    """
    entity_type = change.entity_type
    
    try:
        if entity_type == "module":
            # Cambiar status_module a False
            module = db.query(ModuleCourse).filter(
                ModuleCourse.uuid_module == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not module:
                return False, None, f"Módulo con UUID {change.entity_uuid} no encontrado en el curso target"
            
            module.status_module = False
            return True, module.id_module, None
                
        elif entity_type == "publication":
            # Cambiar status_publish a False SOLO en el curso target
            publication = db.query(CoursePublish).join(
                ModuleCourse
            ).filter(
                CoursePublish.uuid_publish == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not publication:
                return False, None, f"Publicación con UUID {change.entity_uuid} no encontrada en el curso target"
            
            publication.status_publish = False
            return True, publication.id_course_publish, None
                
        elif entity_type == "content":
            # Cambiar status a False SOLO en el curso target
            content = db.query(ContentCoursePublish).join(
                CoursePublish
            ).join(
                ModuleCourse
            ).filter(
                ContentCoursePublish.uuid_content == change.entity_uuid,
                ModuleCourse.id_course == pull_request.id_course_target
            ).first()
            
            if not content:
                return False, None, f"Contenido con UUID {change.entity_uuid} no encontrado en el curso target"
            
            content.status = False
            return True, content.id_content_course_publish, None
        
        elif entity_type == "course":
            # Los cambios del curso se ignoran en la aplicación
            return True, pull_request.id_course_target, None
            
    except Exception as e:
        return False, None, str(e)


def _validate_add_change(db: Session, pull_request: PullRequest, change: PullRequestChange) -> Optional[str]:
    """
    Valida si un cambio ADD puede aplicarse correctamente.
    Retorna error message si hay un problema, None si está todo bien.
    """
    new_data = change.new_data
    entity_type = change.entity_type
    
    # Los cambios de course se ignoran
    if entity_type == "course":
        return None
    
    if entity_type == "module":
        # Validar que el curso target exista
        course = db.query(Course).filter(
            Course.id_course == pull_request.id_course_target
        ).first()
        
        if not course:
            return "Curso target no existe"
        
        # Validar que no exista otro módulo con el mismo UUID
        existing = db.query(ModuleCourse).filter(
            ModuleCourse.uuid_module == change.entity_uuid
        ).first()
        
        if existing:
            return f"Ya existe un módulo con UUID {change.entity_uuid}"
        
        # Validar campos requeridos
        if not new_data.get("name_module"):
            return "El módulo requiere nombre (name_module)"
        if "order_index" not in new_data:
            return "El módulo requiere order_index"
    
    elif entity_type == "publication":
        # Obtener el módulo source
        source_module_id = new_data.get("id_module")
        source_module = db.query(ModuleCourse).filter(
            ModuleCourse.id_module == source_module_id
        ).first()
        
        if not source_module:
            return f"Módulo source con id {source_module_id} no encontrado"
        
        # Validar que el módulo exista en el curso target usando UUID
        target_module = db.query(ModuleCourse).filter(
            ModuleCourse.uuid_module == source_module.uuid_module,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not target_module:
            return f"Módulo con UUID {source_module.uuid_module} no encontrado en el curso target"
        
        # Validar que no exista otra publicación con el mismo UUID
        existing = db.query(CoursePublish).filter(
            CoursePublish.uuid_publish == change.entity_uuid
        ).first()
        
        if existing:
            return f"Ya existe una publicación con UUID {change.entity_uuid}"
        
        # Validar campos requeridos
        if not new_data.get("name_publication"):
            return "La publicación requiere nombre (name_publication)"
    
    elif entity_type == "content":
        # Obtener la publicación source
        source_pub_id = new_data.get("id_course_publish")
        source_pub = db.query(CoursePublish).filter(
            CoursePublish.id_course_publish == source_pub_id
        ).first()
        
        if not source_pub:
            return f"Publicación source con id {source_pub_id} no encontrada"
        
        # Validar que la publicación exista en el curso target usando UUID
        target_pub = db.query(CoursePublish).join(ModuleCourse).filter(
            CoursePublish.uuid_publish == source_pub.uuid_publish,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not target_pub:
            return f"Publicación con UUID {source_pub.uuid_publish} no encontrada en el curso target"
        
        # Validar que no exista otro contenido con el mismo UUID
        existing = db.query(ContentCoursePublish).filter(
            ContentCoursePublish.uuid_content == change.entity_uuid
        ).first()
        
        if existing:
            return f"Ya existe contenido con UUID {change.entity_uuid}"
        
        # Validar campos requeridos
        if not new_data.get("content"):
            return "El contenido no puede estar vacío"
    
    return None


def _validate_update_change(db: Session, pull_request: PullRequest, change: PullRequestChange) -> Optional[str]:
    """
    Valida si un cambio UPDATE puede aplicarse correctamente.
    Retorna error message si hay un problema, None si está todo bien.
    """
    entity_type = change.entity_type
    
    # Los cambios de course se ignoran
    if entity_type == "course":
        return None
    
    if entity_type == "module":
        module = db.query(ModuleCourse).filter(
            ModuleCourse.uuid_module == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not module:
            return f"Módulo con UUID {change.entity_uuid} no encontrado en el curso target"
    
    elif entity_type == "publication":
        pub = db.query(CoursePublish).join(ModuleCourse).filter(
            CoursePublish.uuid_publish == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not pub:
            return f"Publicación con UUID {change.entity_uuid} no encontrada en el curso target"
    
    elif entity_type == "content":
        content = db.query(ContentCoursePublish).join(
            CoursePublish
        ).join(ModuleCourse).filter(
            ContentCoursePublish.uuid_content == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not content:
            return f"Contenido con UUID {change.entity_uuid} no encontrado en el curso target"
    
    return None


def _validate_delete_change(db: Session, pull_request: PullRequest, change: PullRequestChange) -> Optional[str]:
    """
    Valida si un cambio DELETE puede aplicarse correctamente.
    Retorna error message si hay un problema, None si está todo bien.
    """
    entity_type = change.entity_type
    
    # Los cambios de course se ignoran
    if entity_type == "course":
        return None
    
    if entity_type == "module":
        module = db.query(ModuleCourse).filter(
            ModuleCourse.uuid_module == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not module:
            return f"Módulo con UUID {change.entity_uuid} no encontrado en el curso target"
    
    elif entity_type == "publication":
        pub = db.query(CoursePublish).join(ModuleCourse).filter(
            CoursePublish.uuid_publish == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not pub:
            return f"Publicación con UUID {change.entity_uuid} no encontrada en el curso target"
    
    elif entity_type == "content":
        content = db.query(ContentCoursePublish).join(
            CoursePublish
        ).join(ModuleCourse).filter(
            ContentCoursePublish.uuid_content == change.entity_uuid,
            ModuleCourse.id_course == pull_request.id_course_target
        ).first()
        
        if not content:
            return f"Contenido con UUID {change.entity_uuid} no encontrado en el curso target"
    
    return None


@router.get("/{id_pull_request}/applied-changes")
def get_applied_changes(
    id_pull_request: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el audit trail de todos los cambios que se han aplicado a un PR
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
    
    applied_changes = db.query(AppliedChange).options(
        joinedload(AppliedChange.user)
    ).filter(
        AppliedChange.id_pull_request == id_pull_request
    ).order_by(AppliedChange.applied_at).all()
    
    result = []
    for change in applied_changes:
        result.append({
            "id_applied": change.id_applied,
            "id_change": change.id_change,
            "entity_type": change.entity_type,
            "entity_uuid": change.entity_uuid,
            "entity_id": change.entity_id,
            "status": change.status,
            "error_message": change.error_message,
            "applied_at": change.applied_at,
            "applied_by": change.user.name_user if change.user else None
        })
    
    return {
        "id_pull_request": id_pull_request,
        "total_applied": len([r for r in result if r["status"] == "success"]),
        "total_failed": len([r for r in result if r["status"] == "failed"]),
        "applied_changes": result
    }


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