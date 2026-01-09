import json
from typing import Optional
from sqlalchemy.orm import Session
from app.models.course import Course
from sqlalchemy.orm import joinedload
from app.models.module_course import ModuleCourse
from app.models.course_publish import CoursePublish
from app.models.pull_request import PullRequest
from app.models.pullRequestChange import PullRequestChange


def serialize_course_to_snapshot(db: Session, course_id: int) -> str:
    """
    Serializa el curso completo con módulos, publicaciones y contenidos anidados
    usando la estructura de CourseFullResponse
    NOTA: Incluye TODOS los elementos (incluso soft-deleted) para poder detectar cambios de status
    """
    # Obtener curso con todas las relaciones cargadas
    course = db.query(Course).options(
        joinedload(Course.modules)
        .joinedload(ModuleCourse.course_publish)
        .joinedload(CoursePublish.content)
    ).filter(Course.id_course == course_id).first()
    
    if not course:
        raise ValueError(f"Curso con ID {course_id} no encontrado")
    
    # Construir snapshot basado en CourseFullResponse
    snapshot = {
        "id_course": course.id_course,
        "uuid_course": course.uuid_course,
        "name_course": course.name_course,
        "description_course": course.description_course,
        "image": course.image,
        "is_forked": course.is_forked,
        "id_theme": course.id_theme,
        "id_user": course.id_user,
        "id_author_user": course.id_author_user,
        "status_course": course.status_course,
        "date_created": str(course.date_created) if course.date_created else None,
        "date_updated": str(course.date_updated) if course.date_updated else None,
        "modules": []
    }
    
    # Procesar módulos (INCLUYENDO soft-deleted para detectar cambios de status)
    if course.modules:
        for module in sorted(course.modules, key=lambda m: m.order_index or 0):
            module_data = {
                "id_module": module.id_module,
                "uuid_module": module.uuid_module,
                "id_course": module.id_course,
                "name_module": module.name_module,
                "description_module": module.description_module,
                "status_module": module.status_module,
                "order_index": module.order_index,
                "date_created": str(module.date_created) if module.date_created else None,
                "course_publish": []
            }
            
            # Procesar publicaciones
            if module.course_publish:
                for publish in module.course_publish:
                    publish_data = {
                        "id_course_publish": publish.id_course_publish,
                        "uuid_publish": publish.uuid_publish,
                        "id_module": publish.id_module,
                        "name_publication": publish.name_publication,
                        "description": publish.description,
                        "date_created": str(publish.date_created) if publish.date_created else None,
                        "date_updated": str(publish.date_updated) if publish.date_updated else None,
                        "status_publish": publish.status_publish,
                        "content": []
                    }
                    
                    # Procesar contenidos
                    if publish.content:
                        for content in publish.content:
                            content_data = {
                                "id_content_course_publish": content.id_content_course_publish,
                                "uuid_content": content.uuid_content,
                                "id_course_publish": content.id_course_publish,
                                "content": content.content,
                                "status": content.status,
                                "type_content": content.type_content,
                                "date_created": str(content.date_created) if content.date_created else None
                            }
                            publish_data["content"].append(content_data)
                    
                    module_data["course_publish"].append(publish_data)
            
            snapshot["modules"].append(module_data)
    
    # Retornar diccionario (SQLAlchemy se encargará de serializar a JSON)
    return snapshot


def compare_snapshots(old_snapshot: Optional[dict], new_snapshot: dict) -> list:
    """
    Compara dos snapshots y retorna una lista de cambios (diffs)
    old_snapshot y new_snapshot son diccionarios (no strings)
    Detecta eliminaciones lógicas cuando status cambia a false/0
    Solo reporta cambios reales (no duplicados)
    """
    old_snapshot = old_snapshot if old_snapshot else {}
    new_snapshot = new_snapshot if new_snapshot else {}
    
    changes = []
    
    # 1. Comparar datos del curso (incluyendo status para detectar eliminación)
    course_fields = ["name_course", "description_course", "image", "id_theme", "status_course"]
    for field in course_fields:
        old_value = old_snapshot.get(field)
        new_value = new_snapshot.get(field)
        
        if old_value != new_value:
            # Si el status pasa a false/0, registrar como eliminación del curso
            if field == "status_course" and not new_value:
                changes.append({
                    "entity_type": "course",
                    "entity_id": new_snapshot.get("id_course"),
                    "uuid": new_snapshot.get("uuid_course"),
                    "action": "DELETE",
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value
                })
            else:
                changes.append({
                    "entity_type": "course",
                    "entity_id": new_snapshot.get("id_course"),
                    "uuid": new_snapshot.get("uuid_course"),
                    "action": "UPDATE",
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value
                })
    
    # 2. Comparar módulos
    old_modules = {m.get("uuid_module"): m for m in old_snapshot.get("modules", []) if m.get("uuid_module")}
    new_modules = {m.get("uuid_module"): m for m in new_snapshot.get("modules", []) if m.get("uuid_module")}
    
    # Módulos eliminados (por desaparición o por status = false)
    for uuid_module, module in old_modules.items():
        if uuid_module not in new_modules:
            changes.append({
                "entity_type": "module",
                "entity_id": module.get("id_module"),
                "uuid": uuid_module,
                "action": "DELETE",
                "reason": "removed",
                "old_data": module,
                "new_data": None
            })
    
    # Módulos nuevos o modificados
    for uuid_module, new_module in new_modules.items():
        old_module = old_modules.get(uuid_module)
        
        if not old_module:
            # Módulo completamente nuevo
            changes.append({
                "entity_type": "module",
                "entity_id": new_module.get("id_module"),
                "uuid": uuid_module,
                "action": "ADD",
                "old_data": None,
                "new_data": new_module
            })
            # Cuando un módulo es nuevo, todas sus publicaciones y contenidos son nuevos
            # No hay que compararlos por separado
            continue
        
        # ✅ DETECTAR ELIMINACIÓN POR STATUS = FALSE
        old_status = old_module.get("status_module", True)
        new_status = new_module.get("status_module", True)
        
        if old_status and not new_status:
            # Cambio de status True → False = ELIMINACIÓN
            changes.append({
                "entity_type": "module",
                "entity_id": new_module.get("id_module"),
                "uuid": uuid_module,
                "action": "DELETE",
                "reason": "status_disabled",
                "old_data": old_module,
                "new_data": new_module
            })
            continue  # No comparar más propiedades si fue eliminado
        
        # Si el módulo existe en ambos y está activo, comparar propiedades
        if (old_module.get("name_module") != new_module.get("name_module") or
            old_module.get("description_module") != new_module.get("description_module") or
            old_module.get("order_index") != new_module.get("order_index")):
            changes.append({
                "entity_type": "module",
                "entity_id": new_module.get("id_module"),
                "uuid": uuid_module,
                "action": "UPDATE",
                "old_data": old_module,
                "new_data": new_module
            })
    
    # 3. Comparar publicaciones para TODOS los módulos (viejos y nuevos)
    all_module_uuids = set(old_modules.keys()) | set(new_modules.keys())
    
    for uuid_module in all_module_uuids:
        old_module = old_modules.get(uuid_module, {})
        new_module = new_modules.get(uuid_module, {})
        
        old_pubs = {p.get("uuid_publish"): p for p in old_module.get("course_publish", []) if p.get("uuid_publish")}
        new_pubs = {p.get("uuid_publish"): p for p in new_module.get("course_publish", []) if p.get("uuid_publish")}
        
        # Publicaciones eliminadas
        for uuid_pub, pub in old_pubs.items():
            if uuid_pub not in new_pubs:
                changes.append({
                    "entity_type": "publication",
                    "entity_id": pub.get("id_course_publish"),
                    "uuid": uuid_pub,
                    "action": "DELETE",
                    "reason": "removed",
                    "old_data": pub,
                    "new_data": None
                })
        
        # Publicaciones nuevas o modificadas
        for uuid_pub, new_pub in new_pubs.items():
            old_pub = old_pubs.get(uuid_pub)
            
            if not old_pub:
                # Publicación nueva
                changes.append({
                    "entity_type": "publication",
                    "entity_id": new_pub.get("id_course_publish"),
                    "uuid": uuid_pub,
                    "action": "ADD",
                    "old_data": None,
                    "new_data": new_pub
                })
                # Cuando publicación es nueva, todos sus contenidos también son nuevos
                # No hay que compararlos
                continue
            
            # ✅ DETECTAR ELIMINACIÓN POR STATUS = FALSE
            old_status = old_pub.get("status_publish", True)
            new_status = new_pub.get("status_publish", True)
            
            if old_status and not new_status:
                # Cambio de status True → False = ELIMINACIÓN
                changes.append({
                    "entity_type": "publication",
                    "entity_id": new_pub.get("id_course_publish"),
                    "uuid": uuid_pub,
                    "action": "DELETE",
                    "reason": "status_disabled",
                    "old_data": old_pub,
                    "new_data": new_pub
                })
                continue  # No comparar más propiedades si fue eliminado
            
            # Si la publicación existe en ambos y está activa, comparar propiedades
            if (old_pub.get("name_publication") != new_pub.get("name_publication") or
                old_pub.get("description") != new_pub.get("description")):
                changes.append({
                    "entity_type": "publication",
                    "entity_id": new_pub.get("id_course_publish"),
                    "uuid": uuid_pub,
                    "action": "UPDATE",
                    "old_data": old_pub,
                    "new_data": new_pub
                })
        
        # 4. Comparar contenidos para publicaciones que existen en ambos o son nuevas
        for uuid_pub in set(old_pubs.keys()) | set(new_pubs.keys()):
            old_pub = old_pubs.get(uuid_pub, {})
            new_pub = new_pubs.get(uuid_pub, {})
            
            old_contents = {c.get("uuid_content"): c for c in old_pub.get("content", []) if c.get("uuid_content")}
            new_contents = {c.get("uuid_content"): c for c in new_pub.get("content", []) if c.get("uuid_content")}
            
            # Contenidos eliminados
            for uuid_content, content in old_contents.items():
                if uuid_content not in new_contents:
                    changes.append({
                        "entity_type": "content",
                        "entity_id": content.get("id_content_course_publish"),
                        "uuid": uuid_content,
                        "action": "DELETE",
                        "reason": "removed",
                        "old_data": content,
                        "new_data": None
                    })
            
            # Contenidos nuevos o modificados
            for uuid_content, new_content in new_contents.items():
                old_content = old_contents.get(uuid_content)
                
                if not old_content:
                    # Contenido nuevo
                    changes.append({
                        "entity_type": "content",
                        "entity_id": new_content.get("id_content_course_publish"),
                        "uuid": uuid_content,
                        "action": "ADD",
                        "old_data": None,
                        "new_data": new_content
                    })
                else:
                    # ✅ DETECTAR ELIMINACIÓN POR STATUS = FALSE
                    old_status = old_content.get("status", True)
                    new_status = new_content.get("status", True)
                    
                    if old_status and not new_status:
                        # Cambio de status True → False = ELIMINACIÓN
                        changes.append({
                            "entity_type": "content",
                            "entity_id": new_content.get("id_content_course_publish"),
                            "uuid": uuid_content,
                            "action": "DELETE",
                            "reason": "status_disabled",
                            "old_data": old_content,
                            "new_data": new_content
                        })
                    elif (old_content.get("content") != new_content.get("content") or
                        old_content.get("type_content") != new_content.get("type_content")):
                        # Contenido modificado
                        changes.append({
                            "entity_type": "content",
                            "entity_id": new_content.get("id_content_course_publish"),
                            "uuid": uuid_content,
                            "action": "UPDATE",
                            "old_data": old_content,
                            "new_data": new_content
                        })
    
    return changes

def save_changes_to_db(db: Session, pull_request_id: int, changes: list) -> None:
    """
    Guarda los cambios (diffs) en la tabla PullRequestChange
    Valida y convierte los datos al formato correcto
    """
    import json
    
    if not changes:
        return
    
    for change in changes:
        try:
            # Validar datos obligatorios
            if not change.get("entity_type") or not change.get("action"):
                continue
            
            # Preparar valores
            old_value = None
            new_value = None
            
            # Convertir valores simples a string si existen
            if change.get("old_value") is not None:
                old_value = str(change.get("old_value"))
            
            if change.get("new_value") is not None:
                new_value = str(change.get("new_value"))
            
            # Preparar datos JSON (para cambios complejos)
            old_data = None
            new_data = None
            
            if change.get("old_data"):
                old_data = change.get("old_data")
            
            if change.get("new_data"):
                new_data = change.get("new_data")
            
            # Crear registro de cambio
            pr_change = PullRequestChange(
                id_pull_request=pull_request_id,
                entity_type=change.get("entity_type"),
                entity_id=change.get("entity_id"),
                entity_uuid=change.get("uuid"),
                action=change.get("action"),
                reason=change.get("reason"),
                field=change.get("field"),
                old_value=old_value,
                new_value=new_value,
                old_data=old_data,
                new_data=new_data
            )
            db.add(pr_change)
        
        except Exception as e:
            continue
    
    # Un solo commit al final
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise ValueError(f"Error al guardar cambios en la BD: {str(e)}")
