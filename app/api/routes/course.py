from fastapi import APIRouter, Depends, HTTPException, Query
from app.utils.security import get_current_user
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.theme import Theme
from app.models.favorites_course import Favorites
from typing import List, Optional
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse
router = APIRouter()

@router.post("/create_course", response_model=CourseCreate)
def createCourse(course:CourseCreate, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    theme = db.query(Theme).filter(Theme.id_theme == course.id_theme).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    new_course = Course ( name_course = course.name_course, description_course = course.description_course, image = course.image, id_user = current_user.id,
                         is_forked = course.is_forked, id_author_user = current_user.id, id_theme = course.id_theme)
    
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    return new_course

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


