from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from typing import List
from app.models.module_course import ModuleCourse
from app.models.pull_request import PullRequest
from app.utils.security import get_current_user
from app.schemas.user_schema import UserOut
from app.schemas.module_course_schema import ModuleCourseResponse, CreateModule, EditModule
from app.schemas.course_schema import CourseResponse, CourseFullResponse
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.course_publish import CoursePublish
from app.models.favorites_course import Favorites
from app.schemas.publish_course import CoursePublishResponse
from app.services.gemini_services import get_or_generate_summary

router = APIRouter()

@router.get("/detail/{id_course}", response_model=CourseResponse)
def get_detail(
    id_course: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # 1. Buscar curso
    detail_course = db.query(Course).filter(Course.id_course == id_course).first()

    if not detail_course:
        raise HTTPException(status_code=404, detail="No se encontró el curso")

    # 2. ¿El curso es mío?
    is_my_course = current_user and detail_course.id_user == current_user.id
    
    # 3. Obtener promedio y total de calificaciones
    avg_rating = round((
        db.query(func.avg(RatingCommentsCourse.rating))
        .filter(
            RatingCommentsCourse.id_course == id_course,
            RatingCommentsCourse.status == True
        )
        .scalar()
    ) or 0, 1)

    ratings_count = (
        db.query(func.count(RatingCommentsCourse.id_ratings_comments))
        .filter(
            RatingCommentsCourse.id_course == id_course,
            RatingCommentsCourse.status == True
        )
        .scalar()
    ) or 0
    
    # 3.5 Obtener breakdown de calificaciones por estrella
    ratings_breakdown = {
        5: {"count": 0, "percentage": 0},
        4: {"count": 0, "percentage": 0},
        3: {"count": 0, "percentage": 0},
        2: {"count": 0, "percentage": 0},
        1: {"count": 0, "percentage": 0}
    }
    
    if ratings_count > 0:
        for star in range(1, 6):
            count = (
                db.query(func.count(RatingCommentsCourse.id_ratings_comments))
                .filter(
                    RatingCommentsCourse.id_course == id_course,
                    RatingCommentsCourse.rating == star,
                    RatingCommentsCourse.status == True
                )
                .scalar()
            ) or 0
            percentage = (count / ratings_count * 100) if ratings_count > 0 else 0
            ratings_breakdown[star] = {
                "count": count,
                "percentage": round(percentage, 2)
            }

    # Conteo de videos, pdfs, pptx, docx y notas (siempre definidos)
    from app.models.content_course_publish import ContentCoursePublish
    num_videos = db.query(func.count(ContentCoursePublish.id_content_course_publish))\
        .join(CoursePublish, ContentCoursePublish.id_course_publish == CoursePublish.id_course_publish)\
        .join(ModuleCourse, CoursePublish.id_module == ModuleCourse.id_module)\
        .filter(ModuleCourse.id_course == id_course)\
        .filter(CoursePublish.status_publish == True)\
        .filter(func.lower(ContentCoursePublish.type_content) == "video")\
        .filter(ContentCoursePublish.status == True)\
        .scalar() or 0

    num_files = db.query(func.count(ContentCoursePublish.id_content_course_publish))\
        .join(CoursePublish, ContentCoursePublish.id_course_publish == CoursePublish.id_course_publish)\
        .join(ModuleCourse, CoursePublish.id_module == ModuleCourse.id_module)\
        .filter(ModuleCourse.id_course == id_course)\
        .filter(CoursePublish.status_publish == True)\
        .filter(func.lower(ContentCoursePublish.type_content) == "file")\
        .filter(ContentCoursePublish.status == True)\
        .scalar() or 0
    
    num_images = db.query(func.count(ContentCoursePublish.id_content_course_publish))\
        .join(CoursePublish, ContentCoursePublish.id_course_publish == CoursePublish.id_course_publish)\
        .join(ModuleCourse, CoursePublish.id_module == ModuleCourse.id_module)\
        .filter(ModuleCourse.id_course == id_course)\
        .filter(CoursePublish.status_publish == True)\
        .filter(func.lower(ContentCoursePublish.type_content) == "image")\
        .filter(ContentCoursePublish.status == True)\
        .scalar() or 0
    
    num_embed = db.query(func.count(ContentCoursePublish.id_content_course_publish))\
        .join(CoursePublish, ContentCoursePublish.id_course_publish == CoursePublish.id_course_publish)\
        .join(ModuleCourse, CoursePublish.id_module == ModuleCourse.id_module)\
        .filter(ModuleCourse.id_course == id_course)\
        .filter(CoursePublish.status_publish == True)\
        .filter(func.lower(ContentCoursePublish.type_content) == "video-embed")\
        .filter(ContentCoursePublish.status == True)\
        .scalar() or 0

    num_notes = db.query(func.count(ContentCoursePublish.id_content_course_publish))\
        .join(CoursePublish, ContentCoursePublish.id_course_publish == CoursePublish.id_course_publish)\
        .join(ModuleCourse, CoursePublish.id_module == ModuleCourse.id_module)\
        .filter(ModuleCourse.id_course == id_course)\
        .filter(CoursePublish.status_publish == True)\
        .filter(func.lower(ContentCoursePublish.type_content) == "note")\
        .filter(ContentCoursePublish.status == True)\
        .scalar() or 0
    
    # 4. ¿El usuario lo tiene como favorito?
    
    is_favorite = False
    is_my_favorite = False
    if current_user:
        favorite_row = (
            db.query(Favorites)
            .filter(
                Favorites.id_course == id_course,
                Favorites.id_user == current_user.id
            )
            .first()
        )
        is_favorite = bool(favorite_row)
        is_my_favorite = bool(favorite_row)
    author = (
        db.query(User)
        .filter(User.id == detail_course.id_user)
        .first()
    )

    # 6. Crear respuesta con Pydantic
    course_schema = CourseResponse.model_validate(detail_course)

    # 7. Agregar campos calculados
    course_schema.is_my_course = bool(is_my_course)
    course_schema.avg_rating = float(avg_rating)
    course_schema.ratings_count = ratings_count
    course_schema.ratings_breakdown = ratings_breakdown
    course_schema.is_favorite = is_favorite
    course_schema.is_my_favorite = is_my_favorite
    course_schema.status_course = detail_course.status_course
    course_schema.date_updated = detail_course.date_updated
    course_schema.num_videos = num_videos
    course_schema.num_files = num_files
    course_schema.num_embed = num_embed
    course_schema.num_notes = num_notes
    course_schema.num_images = num_images

    return course_schema


@router.get("/modules/{id_course}", response_model=List[ModuleCourseResponse])
def get_modules(id_course:int, db:Session = Depends(get_db)):
    module_course = db.query(ModuleCourse).filter(ModuleCourse.id_course == id_course).order_by(ModuleCourse.order_index.asc()).all()
    if not module_course:
        raise HTTPException(status_code=404, detail="No se tiene modulos este curso")
    return module_course

@router.get("/publications/{id_module}", response_model=List[CoursePublishResponse])
def get_publish(id_module:int,db:Session = Depends(get_db)):
    publish_course = db.query(CoursePublish).filter(CoursePublish.id_module == id_module, CoursePublish.status_publish == 1).all()
    return publish_course

@router.get("/course/raw/{id}", response_model=CourseFullResponse)
async def get_course_raw(id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id_course == id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    return course

@router.get("/summary/{course_id}")
def get_course_summary(course_id: int, db: Session = Depends(get_db)):
    result = get_or_generate_summary(course_id, db)
    return result or {"error": result}

@router.get("/collaboratos/{id_course}", response_model=List[UserOut])
def get_collaborators(id_course:int, db:Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id_course == id_course).first()
    if not course:
        raise HTTPException(status_code=404, detail="No se encontró el curso")
    
    users = db.query(User).distinct().join(
        PullRequest, User.id == PullRequest.id_user
    ).filter(
        PullRequest.id_course_target == id_course,
        PullRequest.merge_status == "merged"
    ).all()
    
    return users