from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from typing import List
from app.models.module_course import ModuleCourse
from app.utils.security import get_current_user
from app.schemas.module_course_schema import ModuleCourseResponse
from app.schemas.course_schema import CourseResponse
from app.models.course_publish import CoursePublish
from app.schemas.publish_course import CoursePublishResponse

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

@router.get("/modules/{id_course}", response_model=List[ModuleCourseResponse])
def get_modules(id_course:int, db:Session = Depends(get_db)):
    module_course = db.query(ModuleCourse).filter(ModuleCourse.id_course == id_course).all()
    if not module_course:
        raise HTTPException(status_code=404, detail="No se tiene modulos este curso")
    return module_course

@router.get("/publications/{id_module}", response_model=List[CoursePublishResponse])
def get_publish(id_module:int,db:Session = Depends(get_db)):
    publish_course = db.query(CoursePublish).filter(CoursePublish.id_module == id_module).all()
    if not publish_course:
        raise HTTPException(status_code=404, detail="No se tiene publicaciones este modulo")
    return publish_course

