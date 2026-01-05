from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.messageOut import MessageResponse
from app.models.rating_comments_course import RatingCommentsCourse
from app.schemas.comments_rating_schema import (
    RatingCommentsCourseCreate,
    RatingCommentsCourseResponse,
    RatingCommentsCourseUpdate
)
from typing import List
from app.utils.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/course/{id_course}", response_model=List[RatingCommentsCourseResponse])
def get_ratings_by_course(id_course: int, db: Session = Depends(get_db)):
    ratings = db.query(RatingCommentsCourse).filter(
        RatingCommentsCourse.id_course == id_course,
        RatingCommentsCourse.status == True
    ).order_by(RatingCommentsCourse.date_created.desc()).all()

    return ratings


@router.get("/{id_rating}", response_model=RatingCommentsCourseResponse)
def get_rating(id_rating: int, db: Session = Depends(get_db)):
    rating = db.query(RatingCommentsCourse).filter(
        RatingCommentsCourse.id_ratings_comments == id_rating
    ).first()

    if not rating:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")

    return rating

@router.delete("/delete_rating_by_id/{id_rating}", response_model=MessageResponse)
def delete_rating_by_id(id_rating: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rating = db.query(RatingCommentsCourse).filter(RatingCommentsCourse.id_ratings_comments == id_rating).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if not rating.id_user == current_user.id:
        raise HTTPException(status_code=403, detail="No puedes eliminar este comentario ya que no te pertenece")

    rating.status = False
    db.commit()
    return {"success": True, "message": "Comentario eliminado correctamente"}

@router.post("/create", response_model=RatingCommentsCourseResponse)
def create_rating(rating_in: RatingCommentsCourseCreate,db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=403, detail="No puedes realizar la accion, no estas logueado")

    new_rating = RatingCommentsCourse(id_course=rating_in.id_course,id_user=current_user.id, comment_detail=rating_in.comment_detail, rating=rating_in.rating)
    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)

    return new_rating

@router.patch("/update/{id_rating}", response_model=RatingCommentsCourseResponse)
def update_rating(id_rating: int,rating_in: RatingCommentsCourseUpdate,db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    rating = db.query(RatingCommentsCourse).filter(RatingCommentsCourse.id_ratings_comments == id_rating).first()

    if not rating:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")

    # Solo el usuario dueño puede editar
    if rating.id_user != current_user.id:
        raise HTTPException(status_code=403, detail="No puedes editar este comentario")

    # Actualizar solo los campos proporcionados
    if rating_in.comment_detail is not None:
        rating.comment_detail = rating_in.comment_detail
    if rating_in.rating is not None:
        rating.rating = rating_in.rating

    db.commit()
    db.refresh(rating)

    return rating