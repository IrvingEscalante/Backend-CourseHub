from fastapi import FastAPI
from app.api.routes import auth
from app.db.session import Base, engine
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import course, detail_course, users
import app.models 
#Crear tablas en mysql si no existen

app=FastAPI(title="CourseHub")

origins = [
    "http://localhost:5173",  # tu frontend Angular
    "http://localhost:4200"  # opcio
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # permitidos
    allow_credentials=True,
    allow_methods=["*"],            # permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],            # permite todos los headers
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(course.router, prefix="/api/course", tags=["Course"])
app.include_router(detail_course.router, prefix="/api/detail_course", tags=["DetailCourse"])