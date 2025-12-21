from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File, Request
from sqlalchemy import or_
from app.utils.security import get_current_user
from sqlalchemy import func
import json
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.user import User
from app.models.course import Course
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.theme import Theme
from app.models.module_course import ModuleCourse
from app.models.course_publish import CoursePublish
from app.models.version_course import CourseVersion
from app.models.content_course_publish import ContentCoursePublish
from app.models.favorites_course import Favorites
from typing import List, Optional, Dict
from app.services.user_services import get_favorite_ids
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local, compress_image
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload, CourseBase
import asyncio
from PIL import Image
import io
import os

router = APIRouter()

@router.post("/pull-request/{id_course_origin}/{id_course_destiny}")
def pull_request(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    hola