from fastapi import UploadFile
import cloudinary
import cloudinary.uploader
from app.core.config import settings
from cloudinary.utils import cloudinary_url

cloudinary.config(
    cloud_name=settings.CLOUD_NAME,
    api_key=settings.API_KEY_CLOUDINARY,
    api_secret=settings.API_SECRET_CLOUDINARY,
    secure=True
)


# ------------------------
# � Función: subir imagen a Cloudinary (portada o recurso)
# Cloudinary optimiza automáticamente - no necesita compresión local
# ------------------------
async def upload_to_cloudinary(file_obj, preset: str):
    # Si es un UploadFile (FastAPI), leer su contenido
    if hasattr(file_obj, 'read') and callable(file_obj.read):
        file_content = await file_obj.read()
    else:
        file_content = file_obj
    
    result = cloudinary.uploader.upload(
        file_content,
        upload_preset=preset,
        resource_type="auto"
    )
    return result["secure_url"]


# ------------------------
# 🟦 Función: guardar archivo local (PDF/PPTX/DOCX/etc)
# ------------------------
async def save_file_local(file: UploadFile, file_name: str):
    save_path = f"static/courses/resources/{file_name}"

    with open(save_path, "wb") as buffer:
        buffer.write(await file.read())

    return f"/static/courses/resources/{file_name}"
