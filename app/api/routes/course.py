from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File, Request
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
from app.core.config import settings
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload
router = APIRouter()

cloudinary.config(
    cloud_name=settings.CLOUD_NAME,
    api_key=settings.API_KEY_CLOUDINARY,
    api_secret=settings.API_SECRET_CLOUDINARY,
    secure=True
)

@router.post("/create")
async def create_course(
    request: Request,
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    if cover is None:
        print("no hay nada en cover")
    
    print(cover)


    form = await request.form()
    
    # ------------------ Obtener payload ------------------
    if "payload" not in form:
        raise HTTPException(400, "Falta el payload")

    data: CoursePayload = CoursePayload.model_validate(json.loads(form["payload"]))

    # ------------------ Detectar archivos ------------------
    # Files: UploadFile
    files_dict = {}

    for key in form:
        val = form.get(key)

        # Cuando es archivo, val.__class__ tiene attribute "filename"
        if hasattr(val, "filename") and val.filename:
            files_dict[key] = val


    # ------------------ Subir portada ------------------
    cover_url = None
    if cover:
        upload_result = cloudinary.uploader.upload(
            file=cover.file,
            folder="courses/covers",
            resource_type="image",
            public_id=cover.filename
        )
        cover_url = upload_result.get("secure_url")
        print("COVER URL:", cover_url)
    else:
        print("no hay cover")


    # ------------ 1. Crear curso ----------------
    new_course = Course(
        name_course=data.title,
        description_course=data.description or "",
        image=cover_url,
        id_user=current_user.id,
        id_author_user=current_user.id,
        id_theme=1,
        is_forked=False,
        status_course=True
    )
    db.add(new_course)
    db.flush()

    # ------------ 2. Crear módulos ----------------
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

        # ------------- 3. Crear publicaciones ---------------
        for publication in module.publications:

            pub = CoursePublish(
                id_module=new_module.id_module,
                name_publication=publication.title,
                description=publication.description,
                status_publish=True
            )
            db.add(pub)
            db.flush()

            # ----------- 4. Crear contenido -------------------
            for res in publication.resources:

                content_value = None

                # 1. Si es archivo subido
                if res.type in ["image", "pdf", "pptx", "video"]:

                    file_key = res.fileKey

                    if file_key not in files_dict:
                        raise HTTPException(400, f"Falta el archivo enviado: {file_key}")

                    file = files_dict[file_key]

                    # Detectar resource_type correcto
                    resource_type = "raw"
                    if res.type == "image":
                        resource_type = "image"
                    elif res.type == "video":
                        resource_type = "video"

                    upload_result = cloudinary.uploader.upload(
                        file.file,
                        folder="courses/resources",
                        resource_type=resource_type
                    )

                    content_value = upload_result["secure_url"]

                else:
                    # 2. Si es texto o link de video
                    content_value = res.value

                # Guardar contenido en BD
                content = ContentCoursePublish(
                    id_course_publish=pub.id_course_publish,
                    content=content_value,
                    status=True
                )
                db.add(content)


    db.commit()

    return {
        "message": "Curso creado exitosamente",
        "course_id": new_course.id_course
    }

@router.get("/courses", response_model=List[CourseResponse])
def get_courses_feed(
    type_query: str = Query("all", enum=["all", "new", "popular", "trending"]),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    # Consulta base: avg_rating y ratings_count
    query = (
        db.query(
            Course,
            func.coalesce(func.avg(RatingCommentsCourse.rating), 0).label("avg_rating"),
            func.count(RatingCommentsCourse.id_ratings_comments).label("ratings_count")
        )
        .outerjoin(RatingCommentsCourse, (RatingCommentsCourse.id_course == Course.id_course) & (RatingCommentsCourse.status == True))
        .group_by(Course.id_course)
    )

    # Orden según tipo de consulta
    if type_query == "new":
        query = query.order_by(Course.date_created.desc())
    elif type_query == "popular":
        query = query.order_by(func.count(RatingCommentsCourse.id_ratings_comments).desc())
    elif type_query == "trending":
        query = query.order_by(Course.date_created.desc())

    # Paginación
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()

    # IDs de cursos favoritos del usuario autenticado
    my_favorite_ids: List[int] = []
    if current_user:
        my_favorite_ids = [
            fav.id_course for fav in db.query(Favorites).filter(Favorites.id_user == current_user.id).all()
        ]

    # Construimos la respuesta
    course_list = [
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
            user=AuthorResponse.model_validate(c.user) if c.user else None
        )
        for c, avg_rating, ratings_count in results
    ]

    return course_list


