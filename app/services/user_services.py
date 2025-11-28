from sqlalchemy.orm import Session
from typing import Optional, List, Set
from sqlalchemy import func
from app.models.user import User
from app.models.course import Course
from app.models.followers import Followers
from app.models.favorites_course import Favorites
from app.schemas.course_schema import AuthorResponse
from app.models.rating_comments_course import RatingCommentsCourse
from app.schemas.course_schema import CourseResponse


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_courses_created(
    db: Session,
    user: User,
    favorite_ids: Optional[Set[int]] = None
) -> List[CourseResponse]:

    query = (
        db.query(
            Course,
            func.coalesce(func.avg(RatingCommentsCourse.rating), 0).label("avg_rating"),
            func.count(RatingCommentsCourse.id_ratings_comments).label("ratings_count"),
        )
        .outerjoin(
            RatingCommentsCourse,
            (RatingCommentsCourse.id_course == Course.id_course)
            & (RatingCommentsCourse.status == True)
        )
        .filter(Course.id_user == user.id)
        .group_by(Course.id_course)
    )

    rows = query.all()

    favorite_ids = favorite_ids or set()

    result = []
    for course, avg_rating, ratings_count in rows:
        result.append(
            CourseResponse(
                id_course=course.id_course,
                name_course=course.name_course,
                description_course=course.description_course,
                image=course.image,
                id_user=course.id_user,
                is_forked=course.is_forked,
                id_author_user=course.id_author_user,
                id_theme=course.id_theme,
                status_course=course.status_course,
                is_my_favorite=(course.id_course in favorite_ids),
                date_created=course.date_created,
                date_updated=course.date_updated,
                avg_rating=float(avg_rating) if avg_rating is not None else None,
                ratings_count=ratings_count,
                author=AuthorResponse.model_validate(course.author) if course.author else None,
                user=AuthorResponse.model_validate(course.user) if course.user else None,
            )
        )
    return result

def get_follow_data(db: Session, user: User, current_user: Optional[User]):
    followers = db.query(Followers).filter(Followers.id_user_follow == user.id).all()
    following = db.query(Followers).filter(Followers.id_user == user.id).all()

    follower_ids = [f.id_user for f in followers]
    following_ids = [f.id_user_follow for f in following]

    is_following = False
    is_mutual = False

    if current_user:
        is_following = db.query(Followers).filter(
            Followers.id_user == current_user.id,
            Followers.id_user_follow == user.id
        ).first() is not None

        is_mutual = is_following and (current_user.id in following_ids)

    return {
        "followers_count": len(follower_ids),
        "following_count": len(following_ids),
        "following": is_following,
        "mutual": is_mutual
    }


def get_favorite_courses(
    db: Session,
    user: User,
    current_user: Optional[User],
    favorite_ids: Optional[set] = None
):
    if not current_user:
        return []

    # Traemos los favoritos del usuario del perfil
    fav_query = (
        db.query(
            Course,
            func.coalesce(func.avg(RatingCommentsCourse.rating), 0).label("avg_rating"),
            func.count(RatingCommentsCourse.id_ratings_comments).label("ratings_count"),
        )
        .join(Favorites, Favorites.id_course == Course.id_course)
        .outerjoin(
            RatingCommentsCourse,
            (RatingCommentsCourse.id_course == Course.id_course)
            & (RatingCommentsCourse.status == True)
        )
        .filter(Favorites.id_user == user.id)  # ← favorito del dueño del perfil
        .group_by(Course.id_course)
    )

    rows = fav_query.all()

    # IMPORTANTE:
    # Solo si ES None, lo reemplazamos
    if favorite_ids is None:
        favorite_ids = set()

    result = []
    for course, avg_rating, ratings_count in rows:
        result.append(
            CourseResponse(
                id_course=course.id_course,
                name_course=course.name_course,
                description_course=course.description_course,
                image=course.image,
                id_user=course.id_user,
                is_forked=course.is_forked,
                id_author_user=course.id_author_user,
                id_theme=course.id_theme,
                status_course=course.status_course,
                # FAVORITO DEL USUARIO LOGUEADO:
                is_my_favorite=(course.id_course in favorite_ids),
                date_created=course.date_created,
                date_updated=course.date_updated,
                avg_rating=float(avg_rating) if avg_rating else None,
                ratings_count=ratings_count,
                author=AuthorResponse.model_validate(course.author) if course.author else None,
                user=AuthorResponse.model_validate(course.user) if course.user else None,
            )
        )

    return result



def get_favorite_ids(db: Session, current_user: Optional[User]):
    if not current_user:
        return []
    return [
        fav.id_course
        for fav in db.query(Favorites).filter(Favorites.id_user == current_user.id).all()
    ]
