from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
import uuid
from typing import List
from app.models.module_course import ModuleCourse
from app.utils.security import get_current_user
from app.schemas.module_course_schema import ModuleCourseResponse, CreateModule, EditModule, ModuleReorderRequest
from app.schemas.course_schema import CourseResponse, CourseFullResponse
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.course_publish import CoursePublish
from app.models.favorites_course import Favorites
from app.schemas.publish_course import CoursePublishResponse

router = APIRouter()


@router.get("/getAll/{id_course}", response_model=List[ModuleCourseResponse])
def get_modules(id_course:int, db:Session = Depends(get_db)):
    module_course = db.query(ModuleCourse).filter(ModuleCourse.id_course == id_course, ModuleCourse.status_module == 1).order_by(ModuleCourse.order_index.asc()).all()
    if not module_course:
        raise HTTPException(status_code=404, detail="No se tiene modulos este curso")
    return module_course

@router.get("/getById/{id_module}", response_model=ModuleCourseResponse)
def get_modules(id_module:int, db:Session = Depends(get_db)):
    module_course = db.query(ModuleCourse).filter(ModuleCourse.id_module == id_module).first()
    if not module_course:
        raise HTTPException(status_code=404, detail="No se encontró el módulo")
    return module_course

@router.post("/create/{id_course}", response_model=List[ModuleCourseResponse])
def create_module(id_course:int, module:CreateModule, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not db.query(Course).filter(Course.id_course == id_course, Course.id_user == current_user.id).first():
        raise HTTPException(status_code=403, detail="Forbidden")
    new_module = ModuleCourse(
        id_course = module.id_course,
        name_module = module.name_module,
        description_module = module.description_module,
        status_module = module.status_module,
        order_index = module.order_index
    )
    db.add(new_module)
    db.commit()
    db.refresh(new_module)
    return [new_module]

@router.put("/edit/{id_module}", response_model=ModuleCourseResponse)
def edit_module(id_module:int, module:EditModule, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    existing_module = db.query(ModuleCourse).filter(ModuleCourse.id_module == id_module).first()
    if not existing_module:
        raise HTTPException(status_code=404, detail="Module not found")
    if not db.query(Course).filter(Course.id_course == existing_module.id_course, Course.id_user == current_user.id).first():
        raise HTTPException(status_code=403, detail="Forbidden")
    if module.name_module is not None:
        existing_module.name_module = module.name_module
    if module.description_module is not None:
        existing_module.description_module = module.description_module
    if module.status_module is not None:
        existing_module.status_module = module.status_module
    if module.order_index is not None:
        existing_module.order_index = module.order_index
    db.commit()
    db.refresh(existing_module)
    return existing_module

@router.patch("/delete/{id_module}", response_model=ModuleCourseResponse)
def delete_module(id_module:int, db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    existing_module = db.query(ModuleCourse).filter(ModuleCourse.id_module == id_module).first()
    if not existing_module:
        raise HTTPException(status_code=404, detail="Module not found")
    if not db.query(Course).filter(Course.id_course == existing_module.id_course, Course.id_user == current_user.id).first():
        raise HTTPException(status_code=403, detail="Forbidden")
    existing_module.status_module = 0
    db.commit()
    db.refresh(existing_module)
    return existing_module


@router.put("/reorder/{id_course}", response_model=list[ModuleCourseResponse])
def reorder_modules(id_course: int, payload: ModuleReorderRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    course = db.query(Course).filter(Course.id_course == id_course, Course.id_user == current_user.id).first()
    if not course:
        raise HTTPException(status_code=403, detail="Forbidden")

    module_ids = [m.id_module for m in payload.modules]
    modules_db = db.query(ModuleCourse).filter(ModuleCourse.id_module.in_(module_ids)).all()

    if len(modules_db) != len(module_ids):
        raise HTTPException(status_code=404, detail="Algunos módulos no existen")

    # Ensure modules belong to the course
    for mod in modules_db:
        if mod.id_course != id_course:
            raise HTTPException(status_code=403, detail="Intento de modificar módulos de otro curso")

    # Apply new order
    order_map = {m.id_module: m.order_index for m in payload.modules}
    for mod in modules_db:
        mod.order_index = order_map.get(mod.id_module, mod.order_index)

    db.commit()

    # Return modules sorted by new order
    modules_db = db.query(ModuleCourse).filter(ModuleCourse.id_course == id_course, ModuleCourse.status_module == 1).order_by(ModuleCourse.order_index.asc()).all()
    return modules_db