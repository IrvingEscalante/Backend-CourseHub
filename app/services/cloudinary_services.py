from fastapi import UploadFile
import cloudinary
import cloudinary.uploader
from app.core.config import settings
from cloudinary.utils import cloudinary_url
from PIL import Image
import io

cloudinary.config(
    cloud_name=settings.CLOUD_NAME,
    api_key=settings.API_KEY_CLOUDINARY,
    api_secret=settings.API_SECRET_CLOUDINARY,
    secure=True
)


# ------------------------
# 🟣 Función: comprimir imagen localmente si es grande
# ------------------------
async def compress_image(upload_file: UploadFile, max_size=1400):
    contents = await upload_file.read()

    try:
        img = Image.open(io.BytesIO(contents))
        img.thumbnail((max_size, max_size))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return buffer
    except Exception:
        return io.BytesIO(contents)

# ------------------------
# 🟩 Función: subir imagen a Cloudinary (portada o recurso)
# ------------------------
async def upload_to_cloudinary(file_obj, preset: str):
    result = cloudinary.uploader.upload(
        file_obj,
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
