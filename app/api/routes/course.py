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
from typing import List, Optional, Dict
from app.services.user_services import get_favorite_ids
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local, compress_image
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload, CourseBase
import asyncio
from PIL import Image
import io
import os

router = APIRouter()

def create_course_version(db: Session, course_id: int, created_by: int) -> CourseVersion:
    version = CourseVersion(
        id_course=course_id,
        version_number=1,  # This will be updated later
        created_by=created_by
    )
    db.add(version)
    db.flush()
    return version

@router.post("/create")
async def create_course(request: Request,cover: UploadFile = File(None),db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    form = await request.form()

    if "payload" not in form:
        raise HTTPException(400, "Falta el payload")

    payload: CoursePayload = CoursePayload.model_validate(
        json.loads(form["payload"])
    )

    files_dict = {
        k: v for k, v in form.items()
        if hasattr(v, "filename") and v.filename
    }

    cover_url = None
    if cover:
        compressed = await compress_image(cover)
        cover_url = await upload_to_cloudinary(
            compressed,
            "coursehub_presets"
        )

    course = Course(
        name_course=payload.title,
        description_course=payload.description or "",
        image=cover_url or "",
        id_user=current_user.id,
        id_author_user=current_user.id,
        id_theme=payload.topic,
        is_forked=False,
        status_course=True
    )
    db.add(course)
    db.flush()
    version = create_course_version(db, course.id_course, current_user.id)
    course.base_version = version.id_version

    upload_tasks = []

    for mi, module in enumerate(payload.modules):

        db_module = ModuleCourse(
            id_course=course.id_course,
            name_module=module.title,
            description_module=module.description or "",
            status_module=True,
            order_index=mi,
        )
        db.add(db_module)
        db.flush()

        for publication in module.publications:

            db_pub = CoursePublish(
                id_module=db_module.id_module,
                name_publication=publication.title,
                description=publication.description or "",
                status_publish=True
            )
            db.add(db_pub)
            db.flush()

            for res in publication.resources:

                async def process_resource(
                    *,
                    resource,
                    pub_id,
                    files
                ):
                    upload_type = resource.type

                    if upload_type in ("image", "archive"):
                        file_key = resource.fileKey

                        if file_key not in files:
                            raise HTTPException(
                                400,
                                f"Falta archivo: {file_key}"
                            )

                        file = files[file_key]
                        file.file.seek(0)

                        if upload_type == "image":
                            comp = await compress_image(file)
                            url = await upload_to_cloudinary(
                                comp,
                                "coursehub_resources_presets"
                            )
                            type_content = "image"
                        else:
                            ext = file.filename.split(".")[-1].lower()
                            name = f"{pub_id}_{file_key}.{ext}"
                            url = await save_file_local(file, name)
                            type_content = ext

                    else:
                        url = resource.value
                        type_content = (
                            "video-embed"
                            if upload_type == "video-embed"
                            else "text"
                        )

                    return {
                        "id_course_publish": pub_id,
                        "content": url,
                        "status": True,
                        "type_content": type_content
                    }

                upload_tasks.append(
                    process_resource(
                        resource=res,
                        pub_id=db_pub.id_course_publish,
                        files=files_dict
                    )
                )

    results = await asyncio.gather(*upload_tasks)

    for r in results:
        content = ContentCoursePublish(**r)
        db.add(content)
        db.flush()

    db.commit()

    return {
        "message": "Curso creado exitosamente",
        "course_id": course.id_course
    }

@router.get("/courses", response_model=List[CourseResponse])
def get_courses_feed(
    type_query: str = Query("all", enum=["all", "new", "popular", "trending"]),
    search: Optional[str] = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    query = (
        db.query(
            Course,
            func.coalesce(func.avg(RatingCommentsCourse.rating), 0).label("avg_rating"),
            func.count(RatingCommentsCourse.id_ratings_comments).label("ratings_count")
        )
        .outerjoin(
            RatingCommentsCourse,
            (RatingCommentsCourse.id_course == Course.id_course) &
            (RatingCommentsCourse.status == True)
        )
        .group_by(Course.id_course)
    )

    # ----------------------------
    # 2. Buscador
    # ----------------------------
    if search:
        search_like = f"%{search}%"
        query = query.filter(
            or_(
                Course.name_course.ilike(search_like),
                Course.description_course.ilike(search_like)
            )
        )
    type_query = "new"
    # ----------------------------
    # 3. Tipos de ordenamiento
    # ----------------------------
    if type_query == "new":
        query = query.order_by(Course.date_created.desc())
    elif type_query == "popular":
        query = query.order_by(func.count(RatingCommentsCourse.id_ratings_comments).desc())
    elif type_query == "trending":
        query = query.order_by(Course.date_created.desc())

    # ----------------------------
    # 4. Paginación
    # ----------------------------
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()

    # ----------------------------
    # 5. Obtener favoritos del usuario
    # ----------------------------
    my_favorite_ids = get_favorite_ids(db, current_user)

    # ----------------------------
    # 6. Construir respuesta final
    # ----------------------------
    course_list = []
    for c, avg_rating, ratings_count in results:
        course_list.append(
            CourseResponse(
                id_course=c.id_course,
                name_course=c.name_course,
                description_course=c.description_course,
                image=c.image,
                id_user=c.id_user,
                is_forked=c.is_forked,
                id_author_user=c.id_author_user,
                id_theme=c.id_theme,
                status_course=c.status_course,
                is_my_favorite=c.id_course in my_favorite_ids,
                date_created=c.date_created,
                date_updated=c.date_updated,
                avg_rating=float(avg_rating),
                ratings_count=ratings_count,
                author=AuthorResponse.model_validate(c.author) if c.author else None,
                user=AuthorResponse.model_validate(c.user) if c.user else None,
            )
        )

    return course_list


@router.post("/copy/{id_course}", response_model=CourseBase)
def copy_course(
    id_course: int,
    db: Session = Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=403, detail="Inicia sesion primero para poder copiar un curso")
    original_course = (
        db.query(Course)
        .options(
            joinedload(Course.modules)
            .joinedload(ModuleCourse.course_publish)
            .joinedload(CoursePublish.content)
        )
        .filter(Course.id_course == id_course, Course.status_course == True)
        .first()
    )
    existing_fork = (
        db.query(Course)
        .filter(
            Course.id_user == current_user.id,
            Course.id_course_parent == original_course.id_course
        )
        .first()
    )

    if existing_fork:
        raise HTTPException(
            409,
            "Ya tienes un fork de este curso"
        )


    if original_course.id_user == current_user.id:
        raise HTTPException(status_code=403, detail="No puedes forkear el curso ya que tu eres el dueño")

    if not original_course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    try:
        base_version = (
            db.query(CourseVersion)
            .filter(CourseVersion.id_course == original_course.id_course)
            .order_by(CourseVersion.version_number.desc())
            .first()
        )
        if not base_version:
            raise HTTPException(
                status_code=400,
                detail="El curso original no tiene versión base"
            )

        new_course = Course(
            id_course_parent=original_course.id_course,
            name_course=original_course.name_course,
            description_course=original_course.description_course,
            image=original_course.image,
            id_user=current_user.id,
            id_author_user=original_course.id_author_user,
            id_theme=original_course.id_theme,
            is_forked=True,
            status_course=True,
        )
        db.add(new_course)
        db.flush()

        fork_version = create_course_version(db, new_course.id_course, current_user.id)
        new_course.base_version = fork_version.id_version

        for module in original_course.modules:
            new_module = ModuleCourse(
                id_course=new_course.id_course,
                name_module=module.name_module,
                description_module=module.description_module,
                status_module=module.status_module,
                order_index=module.order_index
            )
            db.add(new_module)
            db.flush()

            # 4️⃣ Clonar publicaciones
            for publish in module.course_publish:
                new_publish = CoursePublish(
                    id_module=new_module.id_module,
                    name_publication=publish.name_publication,
                    description=publish.description,
                    status_publish=publish.status_publish
                )
                db.add(new_publish)
                db.flush()

                # 5️⃣ Clonar contenido
                for content in publish.content:
                    new_content = ContentCoursePublish(
                        id_course_publish=new_publish.id_course_publish,
                        content=content.content,
                        status=content.status,
                        type_content=content.type_content
                    )
                    db.add(new_content)

        db.commit()

        return new_course

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al hacer fork del curso: {str(e)}"
        )


def has_module_changes(course: Course, modules_payload: List[Dict]) -> bool:
    if len(modules_payload) != len(course.modules):
        return True
    modules_map = {m.id_module: m for m in course.modules}
    for idx, m in enumerate(modules_payload):
        mod = modules_map.get(m.get("id_module"))
        if not mod:
            return True
        if mod.order_index != idx or mod.name_module != m["title"] or mod.description_module != m.get("description", ""):
            return True
        pubs_payload = m.get("publications", [])
        if len(pubs_payload) != len(mod.course_publish):
            return True
        pub_map = {p.id_course_publish: p for p in mod.course_publish}
        for p in pubs_payload:
            pub = pub_map.get(p.get("id_course_publish"))
            if not pub:
                return True
            if pub.name_publication != p["title"] or pub.description != p.get("description", ""):
                return True
            if len(p.get("resources", [])) != len(pub.content):
                return True
    return False


@router.post("/edit/{id_course}")
async def edit_course(
    id_course: int,
    request: Request,
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    course = db.query(Course).options(
        joinedload(Course.modules)
        .joinedload(ModuleCourse.course_publish)
        .joinedload(CoursePublish.content)
    ).filter(Course.id_course == id_course).first()

    if not course:
        raise HTTPException(404, "Curso no encontrado")

    if course.id_user != current_user.id:
        raise HTTPException(403, "No tienes permiso para editar este curso")

    form = await request.form()
    if "payload" not in form:
        raise HTTPException(400, "Falta el payload")

    payload = json.loads(form["payload"])
    modules_payload = payload.get("modules") if isinstance(payload, dict) else []

    course_changed = (
        course.name_course != payload["title"] or
        course.description_course != payload.get("description", "") or
        course.id_theme != payload["topic"] or
        cover is not None
    )
    modules_changed = has_module_changes(course, modules_payload) if isinstance(modules_payload, list) else False

    # Actualizar datos generales
    course.name_course = payload["title"]
    course.description_course = payload.get("description", "")
    course.id_theme = payload["topic"]

    if cover:
        compressed = await compress_image(cover)
        course.image = await upload_to_cloudinary(compressed, "coursehub_presets")

    if not modules_changed:
        db.commit()
        return {"message": "Curso editado exitosamente", "course_id": course.id_course}

    # Crear nueva versión del curso solo si hay cambios en módulos/publicaciones/contenido
    latest_version = db.query(CourseVersion).filter(CourseVersion.id_course == course.id_course)\
                    .order_by(CourseVersion.version_number.desc()).first()
    new_version = create_course_version(db, course.id_course, current_user.id)
    new_version.version_number = (latest_version.version_number + 1) if latest_version else 1
    db.add(new_version)
    db.flush()
    course.base_version = new_version.id_version

    files_dict = {k: v for k, v in form.items() if hasattr(v, "filename") and v.filename}

    # Recorrer módulos
    for mi, m in enumerate(modules_payload):
        original_module = next((mod for mod in course.modules if mod.id_module == m.get("id_module")), None)

        if not original_module or m["title"] != original_module.name_module or m.get("description","") != original_module.description_module:
            db_module = ModuleCourse(
                id_course=course.id_course,
                name_module=m["title"],
                description_module=m.get("description",""),
                status_module=True,
                order_index=mi
            )
            db.add(db_module)
            db.flush()
        else:
            db_module = original_module

        # Publicaciones
        for pi, p in enumerate(m["publications"]):
            original_pub = None
            if original_module:
                original_pub = next((pub for pub in original_module.course_publish if pub.id_course_publish == p.get("id_course_publish")), None)

            if not original_pub or p["title"] != original_pub.name_publication or p.get("description","") != original_pub.description:
                db_pub = CoursePublish(
                    id_module=db_module.id_module,
                    name_publication=p["title"],
                    description=p.get("description",""),
                    status_publish=True
                )
                db.add(db_pub)
                db.flush()
            else:
                db_pub = original_pub

            # Contenidos
            upload_tasks = []
            for ri, r in enumerate(p["resources"]):
                async def process_resource(resource, pub_id):
                    upload_type = resource["type"]
                    if upload_type in ("image", "archive"):
                        file_key = f"67_{resource['fileKey']}"
                        if file_key not in files_dict:
                            raise HTTPException(400, f"Falta archivo: {file_key}.pdf")
                        file = files_dict[file_key]
                        file.file.seek(0)

                        if upload_type == "image":
                            comp = await compress_image(file)
                            url = await upload_to_cloudinary(comp, "coursehub_resources_presets")
                            type_content = "image"
                        else:
                            ext = file.filename.split(".")[-1].lower()
                            name = f"{pub_id}_{file_key}.{ext}"
                            url = await save_file_local(file, name)
                            type_content = ext
                    else:
                        url = resource.get("value")
                        type_content = "video-embed" if upload_type == "video-embed" else "text"

                    return {
                        "id_course_publish": pub_id,
                        "content": url,
                        "status": True,
                        "type_content": type_content
                    }

                upload_tasks.append(process_resource(r, db_pub.id_course_publish))

            results = await asyncio.gather(*upload_tasks)
            for r in results:
                content = ContentCoursePublish(**r)
                db.add(content)
                db.flush()

    db.commit()
    return {"message": "Curso editado exitosamente", "course_id": course.id_course}

@router.patch("/update-basics/{id_course}", response_model=CourseBase)
async def update_course_basics(
    id_course: int,
    name_course: str = Form(None),
    description_course: str = Form(None),
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(name_course)
    print(description_course)
    course = db.query(Course).filter(Course.id_course == id_course).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    if course.id_user != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar este curso")
    
    # Actualizar campos proporcionados (solo si no son None y no están vacíos)
    if name_course is not None and name_course.strip():
        course.name_course = name_course.strip()
    if description_course is not None and description_course.strip():
        course.description_course = description_course.strip()
    
    # Procesar imagen si se proporciona
    if cover:
        compressed = await compress_image(cover)
        course.image = await upload_to_cloudinary(compressed, "coursehub_presets")
    
    db.commit()
    db.refresh(course)
    
    return CourseBase(
        id_course=course.id_course,
        name_course=course.name_course,
        description_course=course.description_course,
        image=course.image,
        id_user=course.id_user,
        id_author_user=course.id_author_user,
        id_theme=course.id_theme,
        is_forked=course.is_forked,
        status_course=course.status_course
    )