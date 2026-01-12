from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.version_course import CourseVersion
from app.models.course import Course
from app.models.user import User
from app.utils.security import get_current_user
from typing import List
from app.schemas.version_course_schema import CourseVersionResponse, CourseVersionListResponse
# Restaurar una versión específica de un curso
from app.models.module_course import ModuleCourse
from app.models.course_publish import CoursePublish
from app.models.content_course_publish import ContentCoursePublish
from app.schemas.version_course_schema import CourseVersionSnapshot
from app.schemas.course_schema import CourseResponse
from app.schemas.module_course_schema import ModuleCourseResponse
from app.schemas.publish_course_schema import PublishCourseResponse
from app.schemas.content_publish import ContentCoursePublishResponse
from sqlalchemy import and_
import json

router = APIRouter()

@router.post("/course/{id_course}/restore/{id_version}")
def restore_course_version(
    id_course: int,
    id_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Restaura el curso y sus relaciones (módulos, publicaciones, contenidos) a partir del snapshot de la versión indicada.
    Las eliminaciones son lógicas (status).
    """
    if not current_user:
        raise HTTPException(status_code=404, detail="Acceso no autorizado")
    # 1. Obtener la versión y snapshot
    version = db.query(CourseVersion).filter(CourseVersion.id_version == id_version, CourseVersion.id_course == id_course).first()
    if not version or not version.snapshot:
        raise HTTPException(status_code=404, detail="Versión o snapshot no encontrado")

    if version.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="No puedes reestablecer la version a un curso que no te pertenece")


    snapshot = version.snapshot if isinstance(version.snapshot, dict) else json.loads(version.snapshot)

    # 2. Actualizar datos del curso principal
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    course.name_course = snapshot.get("name_course", course.name_course)
    course.description_course = snapshot.get("description_course", course.description_course)
    course.image = snapshot.get("image", course.image)
    course.id_theme = snapshot.get("id_theme", course.id_theme)
    course.status_course = snapshot.get("status_course", course.status_course)
    course.is_forked = snapshot.get("is_forked", course.is_forked)
    course.id_author_user = snapshot.get("id_author_user", course.id_author_user)
    course.base_version = id_version

    # 3. Restaurar módulos
    snapshot_modules = snapshot.get("modules", [])
    # Marcar todos los módulos actuales como inactivos (eliminación lógica)
    db.query(ModuleCourse).filter(ModuleCourse.id_course == id_course).update({ModuleCourse.status_module: False})
    db.flush()

    for mod in snapshot_modules:
        db_mod = db.query(ModuleCourse).filter(ModuleCourse.id_module == mod["id_module"]).first()
        if db_mod:
            # Actualizar módulo existente
            db_mod.name_module = mod["name_module"]
            db_mod.description_module = mod["description_module"]
            db_mod.status_module = mod["status_module"]
            db_mod.order_index = mod["order_index"]
            db_mod.date_created = mod["date_created"]
        else:
            # Crear módulo si no existe
            db_mod = ModuleCourse(
                id_module=mod["id_module"],
                id_course=id_course,
                name_module=mod["name_module"],
                description_module=mod["description_module"],
                status_module=mod["status_module"],
                order_index=mod["order_index"],
                date_created=mod["date_created"]
            )
            db.add(db_mod)
        db.flush()

        # 4. Restaurar publicaciones del módulo
        db.query(CoursePublish).filter(CoursePublish.id_module == db_mod.id_module).update({CoursePublish.status_publish: False})
        db.flush()
        for pub in mod.get("course_publish", []):
            db_pub = db.query(CoursePublish).filter(CoursePublish.id_course_publish == pub["id_course_publish"]).first()
            if db_pub:
                db_pub.name_publication = pub["name_publication"]
                db_pub.description = pub["description"]
                db_pub.status_publish = pub["status_publish"]
                db_pub.date_created = pub["date_created"]
                db_pub.date_updated = pub.get("date_updated")
            else:
                db_pub = CoursePublish(
                    id_course_publish=pub["id_course_publish"],
                    id_module=db_mod.id_module,
                    name_publication=pub["name_publication"],
                    description=pub["description"],
                    status_publish=pub["status_publish"],
                    date_created=pub["date_created"],
                    date_updated=pub.get("date_updated")
                )
                db.add(db_pub)
            db.flush()

            # 5. Restaurar contenidos de la publicación
            db.query(ContentCoursePublish).filter(ContentCoursePublish.id_course_publish == db_pub.id_course_publish).update({ContentCoursePublish.status: False})
            db.flush()
            for cont in pub.get("content", []):
                db_cont = db.query(ContentCoursePublish).filter(ContentCoursePublish.id_content_course_publish == cont["id_content_course_publish"]).first()
                if db_cont:
                    db_cont.content = cont["content"]
                    db_cont.status = cont["status"]
                    db_cont.type_content = cont["type_content"]
                    db_cont.date_created = cont["date_created"]
                else:
                    db_cont = ContentCoursePublish(
                        id_content_course_publish=cont["id_content_course_publish"],
                        id_course_publish=db_pub.id_course_publish,
                        content=cont["content"],
                        status=cont["status"],
                        type_content=cont["type_content"],
                        date_created=cont["date_created"]
                    )
                    db.add(db_cont)
                db.flush()

    db.commit()

    return {"detail": f"Curso restaurado a la versión {id_version}", "id_course": id_course, "id_version": id_version}

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
    if not current_user:
        raise HTTPException(status_code=404, detail="Acceso no autorizado")
    # Verificar que el curso existe
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    # Obtener versiones ordenadas descendentemente
    versions = db.query(CourseVersion)\
        .filter(CourseVersion.id_course == id_course,CourseVersion.created_by == current_user.id)\
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
    if not current_user:
        raise HTTPException(status_code=404, detail="Acceso no autorizado")
    # Buscar la versión
    version = db.query(CourseVersion)\
        .filter(
            CourseVersion.id_version == id_version,
            CourseVersion.id_course == id_course,
            CourseVersion.created_by == current_user.id
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
    if not current_user:
        raise HTTPException(status_code=404, detail="Acceso no autorizado")
    # Verificar que el curso existe
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    # Obtener la versión con el mayor version_number
    latest_version = db.query(CourseVersion)\
        .filter(CourseVersion.id_course == id_course, CourseVersion.created_by == current_user.id)\
        .order_by(CourseVersion.version_number.desc())\
        .first()
    
    if not latest_version:
        raise HTTPException(status_code=404, detail="No hay versiones disponibles para este curso")
    
    return latest_version
