from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.utils.security import get_current_user
from app.schemas.course_schema import CourseResponse

router = APIRouter()

@router.get("/detail/{id_course}", response_model=CourseResponse)
def get_detail(id_course:int, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    
    detail_course = db.query(Course).filter(Course.id_course == id_course).first()
    
    if not detail_course:
        raise HTTPException(status_code=404, detail="No se encontró el curso")
    
    is_my_course = current_user and detail_course.id_user == current_user.id

    course_schema = CourseResponse.model_validate(detail_course)

    course_schema.is_my_course = bool(is_my_course)

    return course_schema