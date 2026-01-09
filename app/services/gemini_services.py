from google import genai
from app.core.config import settings
from app.models.course_summary_cache import CourseSummaryCache
from app.models.course import Course
from app.models.rating_comments_course import RatingCommentsCourse
from datetime import datetime, timedelta
import os
import time

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def generate_text(prompt: str) -> str:
    """Genera texto con reintentos en caso de límite de cuota"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            
            # Si es error 429 (cuota excedida), esperar y reintentar
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # backoff exponencial
                    time.sleep(wait_time)
                    continue            
            raise


def get_or_generate_summary(course_id: int, db_session, force_refresh: bool = False):
    """
    Obtiene el resumen del caché o lo genera si es necesario.
    
    Args:
        course_id: ID del curso
        db_session: Sesión de base de datos
        force_refresh: Forzar generación nueva sin usar caché
    
    Returns:
        dict con 'summary', 'average_rating' y 'comment_count', o None si no hay suficientes comentarios
    """
    
    # Obtener el curso
    course = db_session.query(Course).filter(Course.id_course == course_id).first()
    if not course:
        return None
    comments = db_session.query(RatingCommentsCourse).filter(
        RatingCommentsCourse.id_course == course_id,
        RatingCommentsCourse.status == True
    ).order_by(RatingCommentsCourse.date_created.desc()).limit(100).all()
    
    # Validar que haya más de 1 comentario
    if len(comments) <= 1:
        return None
    
    # Buscar en caché
    cached = db_session.query(CourseSummaryCache).filter(
        CourseSummaryCache.course_id == course_id
    ).first()
    
    # Si existe caché y no ha pasado 24 horas, retornar caché
    if cached and not force_refresh:
        time_diff = datetime.now() - cached.last_updated
        if time_diff < timedelta(hours=24):
            return {
                "summary": cached.summary,
                "average_rating": cached.average_rating,
                "comment_count": cached.comment_count
            }
    
    # Generar nuevo resumen
    comments_text = "\n".join([
        f"Rating: {c.rating}/5 - {c.comment_detail}" for c in comments
    ])
    
    average_rating = sum([c.rating for c in comments]) / len(comments) if comments else 0
    
    prompt = f"""
    Analiza estos comentarios de un curso (últimos 100) y proporciona un resumen conciso en español:
    
    Rating promedio: {average_rating:.1f}/5
    Total de comentarios: {len(comments)}
    
    Comentarios:
    {comments_text}
    
    Proporciona un resumen que incluya:
    1. Temas principales mencionados
    2. Puntos positivos del curso
    3. Áreas de mejora sugeridas
    
    Mantén el resumen conciso y relevante, no incluyas viñetas ni otros simbolos, solo general el resumen.
    """
    
    try:
        summary = generate_text(prompt)
    except Exception as e:
        return None
    
    # Guardar o actualizar en caché
    cache_entry = db_session.query(CourseSummaryCache).filter(
        CourseSummaryCache.course_id == course_id
    ).first()
    
    if cache_entry:
        cache_entry.summary = summary
        cache_entry.average_rating = average_rating
        cache_entry.comment_count = len(comments)
        cache_entry.last_updated = datetime.now()
    else:
        cache_entry = CourseSummaryCache(
            course_id=course_id,
            summary=summary,
            average_rating=average_rating,
            comment_count=len(comments)
        )
        db_session.add(cache_entry)
    
    db_session.commit()
    
    return {
        "summary": summary,
        "average_rating": average_rating,
        "comment_count": len(comments)
    }



