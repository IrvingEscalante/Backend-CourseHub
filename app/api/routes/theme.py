from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from typing import List
from app.models.module_course import ModuleCourse
from app.utils.security import get_current_user
from app.schemas.theme_schema import ThemeResponse
from app.models.theme import Theme
router = APIRouter()

@router.get("/", response_model=List[ThemeResponse])
def get_themes(db:Session = Depends(get_db)):
    themes = db.query(Theme).all()
    if not themes:
        raise HTTPException(status_code=404, detail="No hay temas para mostrar")
    return themes
