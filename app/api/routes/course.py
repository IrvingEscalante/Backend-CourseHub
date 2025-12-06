from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File, Request
from sqlalchemy import or_
from app.utils.security import get_current_user
from sqlalchemy import func
import json
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.theme import Theme
from app.models.module_course import ModuleCourse
from app.models.course_publish import CoursePublish
from app.models.content_course_publish import ContentCoursePublish
from app.models.favorites_course import Favorites
from typing import List, Optional, Dict
import cloudinary
from app.services.user_services import get_favorite_ids
from app.core.config import settings
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload
import asyncio
from PIL import Image
import io
import os

router = APIRouter()

cloudinary.config(
    cloud_name=settings.CLOUD_NAME,
    api_key=settings.API_KEY_CLOUDINARY,
    api_secret=settings.API_SECRET_CLOUDINARY,
    secure=True
)


# ------------------------
# 🟣 Función: comprimir imagen localmente si es grande
# ------------------------
async def compress_image(upload_file: UploadFile, max_size=1400):
    try:
        img = Image.open(upload_file.file)
        img.thumbnail((max_size, max_size))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        return buffer
    except:
        upload_file.file.seek(0)
        return upload_file.file  # fallback, subir original


# ------------------------
# 🟩 Función: subir imagen a Cloudinary (portada o recurso)
# ------------------------
async def upload_to_cloudinary(file_obj, preset: str):
    return cloudinary.uploader.upload(
        file_obj,
        upload_preset=preset
    )["secure_url"]


# ------------------------
# 🟦 Función: guardar archivo local (PDF/PPTX/DOCX/etc)
# ------------------------
async def save_file_local(file: UploadFile, file_name: str):
    save_path = f"static/courses/resources/{file_name}"

    with open(save_path, "wb") as buffer:
        buffer.write(await file.read())

    return f"/static/courses/resources/{file_name}"


# ---------------------------------------------------
# 🚀 ENDPOINT OPTIMIZADO
# ---------------------------------------------------
@router.post("/create")
async def create_course(
    request: Request,
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    form = await request.form()

    if "payload" not in form:
        raise HTTPException(400, "Falta el payload")

    data: CoursePayload = CoursePayload.model_validate(json.loads(form["payload"]))

    # Obtener archivos enviados
    files_dict = {k: v for k, v in form.items() if hasattr(v, "filename") and v.filename}

    # -----------------------------
    # 1️⃣ Subir portada (optimizado)
    # -----------------------------
    cover_url = None
    if cover:
        compressed = await compress_image(cover)
        cover_url = await upload_to_cloudinary(compressed, "coursehub_presets")

    # -----------------------------
    # 2️⃣ Crear curso
    # -----------------------------
    new_course = Course(
        name_course=data.title,
        description_course=data.description or "",
        image=cover_url,
        id_user=current_user.id,
        id_author_user=current_user.id,
        id_theme=data.topic,
        is_forked=False,
        status_course=True
    )
    db.add(new_course)
    db.flush()

    # ------------------------------------------------------
    # 3️⃣ Crear módulos, publicaciones y recursos (PARALELO)
    # ------------------------------------------------------
    upload_tasks = []  # se llenará con tareas async

    for index_m, module in enumerate(data.modules):

        new_module = ModuleCourse(
            id_course=new_course.id_course,
            name_module=module.title,
            description_module=module.description,
            status_module=True,
            order_index=index_m
        )
        db.add(new_module)
        db.flush()

        for publication in module.publications:

            pub = CoursePublish(
                id_module=new_module.id_module,
                name_publication=publication.title,
                description=publication.description,
                status_publish=True
            )
            db.add(pub)
            db.flush()

            for res in publication.resources:

                file_key = res.fileKey
                upload_type = res.type

                async def process_resource(res=res, pub=pub):
                    # Es archivo subido
                    if upload_type in ["image", "archive", "video", "raw"]:
                        if file_key not in files_dict:
                            raise HTTPException(400, f"Falta archivo: {file_key}")

                        file = files_dict[file_key]

                        # IMAGEN → Cloudinary (optimizado)
                        if upload_type == "image":
                            comp = await compress_image(file)
                            url = await upload_to_cloudinary(comp, "coursehub_resources_presets")
                            type_content = "image"

                        else:
                            # PDF/PPTX/DOCX → local
                            ext = file.filename.split(".")[-1].lower()
                            file_name = f"{pub.id_course_publish}_{file_key}.{ext}"
                            url = await save_file_local(file, file_name)
                            type_content = ext

                    else:
                        # Texto o embed
                        url = res.value
                        type_content = "text"
                        
                        if upload_type == "video-embed":
                            url = res.value
                            type_content = "video-embed"

                    # Insertar contenido
                    db.add(ContentCoursePublish(
                        id_course_publish=pub.id_course_publish,
                        content=url,
                        status=True,
                        type_content=type_content
                    ))

                upload_tasks.append(process_resource())

    # Esperar todas las subidas en paralelo
    await asyncio.gather(*upload_tasks)

    db.commit()

    return {"message": "Curso creado exitosamente", "course_id": new_course.id_course}

@router.get("/courses", response_model=List[CourseResponse])
def get_courses_feed(
    type_query: str = Query("all", enum=["all", "new", "popular", "trending"]),
    search: Optional[str] = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    # ----------------------------
    # 1. Consulta base cursos + rating
    # ----------------------------
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
