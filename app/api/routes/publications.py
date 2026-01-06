from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.course import Course
import uuid
from app.models.user import User
from app.models.module_course import ModuleCourse
from typing import List, Optional
from app.models.course_publish import CoursePublish
from app.models.content_course_publish import ContentCoursePublish
from app.utils.security import get_current_user
from app.schemas.publish_course_schema import PublishCourseResponse, CreatePublicationRequest
from app.schemas.course_schema import CourseResponse, CourseFullResponse
from app.models.rating_comments_course import RatingCommentsCourse
from app.models.favorites_course import Favorites
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local
import json

router = APIRouter()

@router.get("/getById/{id_publication}", response_model=PublishCourseResponse)
def get_publication_by_id(id_publication:int, db:Session = Depends(get_db)):
    
    publication = db.query(CoursePublish).filter(CoursePublish.id_course_publish == id_publication).first()
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")
    return publication

@router.patch("/delete/{id_publication}", response_model=PublishCourseResponse)
def delete_publication(id_publication: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Obtener publicación
    publication = db.query(CoursePublish).filter(CoursePublish.id_course_publish == id_publication).first()
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # Verificar propiedad en una línea
    is_owner = db.query(Course).join(ModuleCourse).filter(ModuleCourse.id_module == publication.id_module, Course.id_user == current_user.id).first()
    if not is_owner:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Soft delete
    publication.status_publish = False
    db.query(ContentCoursePublish).filter(ContentCoursePublish.id_course_publish == id_publication).update({"status": False})
    
    db.commit()
    db.refresh(publication)
    
    return publication

@router.post("/create/{id_module}", response_model=PublishCourseResponse)
async def create_publication(
    id_module: int,
    name_publication: str = Form(...),
    description: str = Form(...),
    contents_metadata: str = Form(...),  # JSON string con metadatos de contenidos
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crear una publicación con múltiples contenidos.
    
    contents_metadata debe ser un JSON array con objetos:
    [
        {"type": "image", "file_index": 0},
        {"type": "video", "file_index": 1},
        {"type": "video-embed", "videoUrl": "https://www.youtube.com/watch?v=..."},
        {"type": "note", "text": "Contenido de la nota"},
        {"type": "file", "file_index": 2}
    ]
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Verificar que el módulo existe y pertenece a un curso del usuario
    module = db.query(ModuleCourse).filter(ModuleCourse.id_module == id_module).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    course = db.query(Course).filter(Course.id_course == module.id_course, Course.id_user == current_user.id).first()
    if not course:
        raise HTTPException(status_code=403, detail="Forbidden - You don't own this course")
    
    # Parsear metadatos de contenidos
    try:
        contents_data = json.loads(contents_metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid contents_metadata format")
    
    # Crear la publicación
    new_publication = CoursePublish(
        id_module=id_module,
        name_publication=name_publication,
        description=description,
        status_publish=True
    )
    db.add(new_publication)
    db.commit()
    db.refresh(new_publication)
    
    # Procesar cada contenido
    for content_item in contents_data:
        content_type = content_item.get("type")
        content_value = ""
        
        if content_type == "image":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Subir imagen a Cloudinary (sin compresión local)
                content_value = await upload_to_cloudinary(file, "coursehub_resources_presets")
        
        elif content_type == "video":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Subir video a Cloudinary
                content_value = await upload_to_cloudinary(file, "coursehub_resources_presets")
        
        elif content_type == "video-embed":
            # Video embebido de YouTube
            content_value = content_item.get("url", "")
        
        elif content_type == "note":
            content_value = content_item.get("text", "")
        
        elif content_type == "file":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Guardar archivo localmente
                file_name = f"{new_publication.id_course_publish}_{file.filename}"
                content_value = await save_file_local(file, file_name)
        
        # Crear registro de contenido
        if content_value:
            new_content = ContentCoursePublish(
                uuid_content=str(uuid.uuid4()),
                id_course_publish=new_publication.id_course_publish,
                content=content_value,
                type_content=content_type,
                status=True
            )
            db.add(new_content)
    
    db.commit()
    db.refresh(new_publication)
    
    return new_publication


@router.delete("/content/{id_content}")
def delete_content(
    id_content: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un contenido específico de una publicación"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    content = db.query(ContentCoursePublish).filter(
        ContentCoursePublish.id_content_course_publish == id_content
    ).first()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Verificar propiedad
    publication = db.query(CoursePublish).filter(
        CoursePublish.id_course_publish == content.id_course_publish
    ).first()
    
    if publication:
        module = db.query(ModuleCourse).filter(ModuleCourse.id_module == publication.id_module).first()
        if module:
            course = db.query(Course).filter(
                Course.id_course == module.id_course,
                Course.id_user == current_user.id
            ).first()
            if not course:
                raise HTTPException(status_code=403, detail="Forbidden")
    
    db.delete(content)
    db.commit()
    
    return {"message": "Content deleted successfully"}


@router.patch("/edit/{id_publication}", response_model=PublishCourseResponse)
async def edit_publication(
    id_publication: int,
    name_publication: str = Form(...),
    description: str = Form(...),
    contents_metadata: str = Form(...),  # JSON con metadatos de contenidos (nuevos y existentes)
    deleted_content_ids: str = Form(default="[]"),  # JSON array con IDs de contenidos a eliminar
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Editar una publicación y sus contenidos.
    
    contents_metadata debe ser un JSON array con objetos:
    [
        {"type": "image", "file_index": 0},  # Nuevo contenido con archivo
        {"type": "video", "file_index": 1},  # Nuevo contenido de video
        {"type": "video-embed", "videoUrl": "https://www.youtube.com/watch?v=..."},  # Video embebido
        {"type": "note", "text": "Contenido de la nota"},  # Nuevo contenido de nota
        {"type": "image", "existing_id": 123},  # Contenido existente que se mantiene
    ]
    
    deleted_content_ids: JSON array con IDs de contenidos a eliminar
    ["1", "2", "3"]
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Obtener la publicación
    publication = db.query(CoursePublish).filter(
        CoursePublish.id_course_publish == id_publication
    ).first()
    
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # Verificar propiedad
    module = db.query(ModuleCourse).filter(ModuleCourse.id_module == publication.id_module).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    course = db.query(Course).filter(
        Course.id_course == module.id_course,
        Course.id_user == current_user.id
    ).first()
    if not course:
        raise HTTPException(status_code=403, detail="Forbidden - You don't own this course")
    
    # Actualizar datos básicos de la publicación
    publication.name_publication = name_publication
    publication.description = description
    
    # Parsear metadatos de contenidos
    try:
        contents_data = json.loads(contents_metadata)
        deleted_ids = json.loads(deleted_content_ids)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    # Eliminar contenidos marcados para eliminación
    for content_id in deleted_ids:
        content_to_delete = db.query(ContentCoursePublish).filter(
            ContentCoursePublish.id_content_course_publish == int(content_id),
            ContentCoursePublish.id_course_publish == id_publication
        ).first()
        if content_to_delete:
            db.delete(content_to_delete)
    
    # Procesar cada contenido (solo los nuevos, los existentes ya están en BD)
    for content_item in contents_data:
        # Si tiene existing_id, es un contenido existente que se mantiene
        if content_item.get("existing_id"):
            continue
            
        content_type = content_item.get("type")
        content_value = ""
        
        if content_type == "image":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Subir imagen a Cloudinary
                content_value = await upload_to_cloudinary(file, "coursehub_resources_presets")
        
        elif content_type == "video":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Subir video a Cloudinary
                content_value = await upload_to_cloudinary(file, "coursehub_resources_presets")
        
        elif content_type == "video-embed":
            # Video embebido de YouTube
            content_value = content_item.get("url", "")
        
        elif content_type == "note":
            content_value = content_item.get("text", "")
        
        elif content_type == "file":
            file_index = content_item.get("file_index")
            if file_index is not None and file_index < len(files):
                file = files[file_index]
                # Guardar archivo localmente
                file_name = f"{publication.id_course_publish}_{file.filename}"
                content_value = await save_file_local(file, file_name)
        
        # Crear nuevo registro de contenido
        if content_value:
            new_content = ContentCoursePublish(
                id_course_publish=publication.id_course_publish,
                content=content_value,
                type_content=content_type,
                status=True
            )
            db.add(new_content)
    
    db.commit()
    db.refresh(publication)
    
    return publication