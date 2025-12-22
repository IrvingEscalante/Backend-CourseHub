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
from app.models.pull_request import PullRequest
from app.models.pullRequestChange import PullRequestChange
from typing import List, Optional, Dict
from app.services.user_services import get_favorite_ids
from app.services.cloudinary_services import upload_to_cloudinary, save_file_local, compress_image
from app.schemas.course_schema import CourseCreate , CourseResponse, AuthorResponse, CoursePayload, CourseBase
from app.schemas.pull_request_schema import PullRequestCreate
import asyncio
from PIL import Image
import io
import os

router = APIRouter()

@router.post("/", status_code=201)
def create_pull_request(
    data: PullRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    source = db.query(Course).filter(Course.id_course == data.id_course_source).first()  # curso con cambios
    target = db.query(Course).filter(Course.id_course == data.id_course_target).first()  # curso original


    if not source or not target:
        raise HTTPException(404, "Source or target course not found")



    # 3️⃣ Obtener versiones actuales (CONGELADAS)
    source_version = db.query(CourseVersion).filter(
        CourseVersion.id_course == source.id_course
    ).order_by(CourseVersion.created_at.desc()).first()

    target_version = db.query(CourseVersion).filter(
        CourseVersion.id_course == target.id_course
    ).order_by(CourseVersion.created_at.desc()).first()

    if not source_version or not target_version:
        raise HTTPException(
            400,
            "Both courses must have at least one version"
        )

    # 4️⃣ Evitar PR duplicados sobre las MISMAS versiones
    existing_pr = db.query(PullRequest).filter(
        PullRequest.source_version_id == source_version.id_version,
        PullRequest.target_version_id == target_version.id_version,
        PullRequest.status_pull == "open"
    ).first()

    if existing_pr:
        raise HTTPException(
            400,
            "There is already an open pull request for these versions"
        )

    # 5️⃣ Crear PR (AHORA SÍ COMPLETO)
    pull_request = PullRequest(
        id_course_source=source.id_course,
        id_course_target=target.id_course,
        source_version_id=source_version.id_version,
        target_version_id=target_version.id_version,
        title=data.title,
        description_pull_request=data.description,
        id_user=current_user.id,
        status_pull="open"
    )

    db.add(pull_request)
    db.commit()
    db.refresh(pull_request)

    # 6️⃣ Generar cambios (diff)
    generate_pull_request_changes(
        db=db,
        pull_request=pull_request,
        source_version=source_version,
        target_version=target_version
    )

    return pull_request

def generate_pull_request_changes(db, pull_request, source_version, target_version):
    """
    Genera los cambios de un pull request entre source_version y target_version.
    Maneja ADD, UPDATE y DELETE para módulos, publicaciones y contenido,
    incluso si los id_original_* son nulos.
    """

    # ---------------- MÓDULOS ----------------
    # Mapear módulos: usar id_original_module si existe, si no usar id_module
    def map_modules(modules):
        mapping = {}
        for m in modules:
            key = m.id_original_module or m.id_module
            mapping[key] = m
        return mapping

    source_modules = map_modules(target_version.modules)
    target_modules = map_modules(source_version.modules)

    # Procesar ADD/UPDATE módulos
    for key, src_mod in source_modules.items():
        tgt_mod = target_modules.get(key)
        if not tgt_mod:
            # Nuevo módulo
            db.add(PullRequestChange(
                id_pull_request=pull_request.id_pull_request,
                entity_type="module",
                entity_id=src_mod.id_module,
                action="ADD",
                old_data=None,
                new_data={"name": src_mod.name_module, "description": src_mod.description_module}
            ))
        else:
            updates = {}
            if src_mod.name_module != tgt_mod.name_module:
                updates["name"] = {"old": tgt_mod.name_module, "new": src_mod.name_module}
            if src_mod.description_module != tgt_mod.description_module:
                updates["description"] = {"old": tgt_mod.description_module, "new": src_mod.description_module}
            if updates:
                db.add(PullRequestChange(
                    id_pull_request=pull_request.id_pull_request,
                    entity_type="module",
                    entity_id=src_mod.id_module,
                    action="UPDATE",
                    old_data={k: v["old"] for k, v in updates.items()},
                    new_data={k: v["new"] for k, v in updates.items()}
                ))

    # DELETE módulos
    for key, tgt_mod in target_modules.items():
        if key not in source_modules:
            db.add(PullRequestChange(
                id_pull_request=pull_request.id_pull_request,
                entity_type="module",
                entity_id=tgt_mod.id_module,
                action="DELETE",
                old_data={"name": tgt_mod.name_module, "description": tgt_mod.description_module},
                new_data=None
            ))

    # ---------------- PUBLICACIONES Y CONTENIDO ----------------
    for key, src_mod in source_modules.items():
        tgt_mod = target_modules.get(key)

        src_pubs = {}
        for p in src_mod.course_publish:
            pub_key = getattr(p, "id_original_publish", None) or p.name_publication
            src_pubs[pub_key] = p

        tgt_pubs = {}
        if tgt_mod:
            for p in tgt_mod.course_publish:
                pub_key = getattr(p, "id_original_publish", None) or p.name_publication
                tgt_pubs[pub_key] = p

        # ADD / UPDATE publicaciones
        for pub_key, src_pub in src_pubs.items():
            tgt_pub = tgt_pubs.get(pub_key)
            if not tgt_pub:
                db.add(PullRequestChange(
                    id_pull_request=pull_request.id_pull_request,
                    entity_type="publish",
                    entity_id=src_pub.id_course_publish,
                    action="ADD",
                    old_data=None,
                    new_data={"name": src_pub.name_publication, "description": src_pub.description}
                ))
            else:
                updates = {}
                if src_pub.name_publication != tgt_pub.name_publication:
                    updates["name"] = {"old": tgt_pub.name_publication, "new": src_pub.name_publication}
                if src_pub.description != tgt_pub.description:
                    updates["description"] = {"old": tgt_pub.description, "new": src_pub.description}
                if updates:
                    db.add(PullRequestChange(
                        id_pull_request=pull_request.id_pull_request,
                        entity_type="publish",
                        entity_id=src_pub.id_course_publish,
                        action="UPDATE",
                        old_data={k: v["old"] for k, v in updates.items()},
                        new_data={k: v["new"] for k, v in updates.items()}
                    ))

            # Contenido de cada publicación
            src_contents = {}
            for c in src_pub.content:
                cont_key = getattr(c, "id_original_content", None) or c.content
                src_contents[cont_key] = c

            tgt_contents = {}
            if tgt_pub:
                for c in tgt_pub.content:
                    cont_key = getattr(c, "id_original_content", None) or c.content
                    tgt_contents[cont_key] = c

            # ADD / UPDATE contenido
            for cont_key, src_cont in src_contents.items():
                tgt_cont = tgt_contents.get(cont_key)
                if not tgt_cont:
                    db.add(PullRequestChange(
                        id_pull_request=pull_request.id_pull_request,
                        entity_type="content",
                        entity_id=src_cont.id_content_course_publish,
                        action="ADD",
                        old_data=None,
                        new_data={"content": src_cont.content, "type": src_cont.type_content}
                    ))
                else:
                    if src_cont.content != tgt_cont.content or src_cont.type_content != tgt_cont.type_content:
                        db.add(PullRequestChange(
                            id_pull_request=pull_request.id_pull_request,
                            entity_type="content",
                            entity_id=src_cont.id_content_course_publish,
                            action="UPDATE",
                            old_data={"content": tgt_cont.content, "type": tgt_cont.type_content},
                            new_data={"content": src_cont.content, "type": src_cont.type_content}
                        ))

            # DELETE contenido
            for cont_key, tgt_cont in tgt_contents.items():
                if cont_key not in src_contents:
                    db.add(PullRequestChange(
                        id_pull_request=pull_request.id_pull_request,
                        entity_type="content",
                        entity_id=tgt_cont.id_content_course_publish,
                        action="DELETE",
                        old_data={"content": tgt_cont.content, "type": tgt_cont.type_content},
                        new_data=None
                    ))

        # DELETE publicaciones
        for pub_key, tgt_pub in tgt_pubs.items():
            if pub_key not in src_pubs:
                db.add(PullRequestChange(
                    id_pull_request=pull_request.id_pull_request,
                    entity_type="publish",
                    entity_id=tgt_pub.id_course_publish,
                    action="DELETE",
                    old_data={"name": tgt_pub.name_publication, "description": tgt_pub.description},
                    new_data=None
                ))

    db.commit()
