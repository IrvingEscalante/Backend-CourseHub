from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import auth
from app.db.session import Base, engine
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import course, detail_course, users, theme, rating_comments, favorites
import app.models 
#Crear tablas en mysql si no existen

app=FastAPI(title="CourseHub")

origins = [
    "http://localhost:4200",  # tu frontend Angular
    "http://localhost:4200"  # opcio
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # permitidos
    allow_credentials=True,
    allow_methods=["*"],            # permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],            # permite todos los headers
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(course.router, prefix="/api/course", tags=["Course"])
app.include_router(detail_course.router, prefix="/api/detail_course", tags=["DetailCourse"])
app.include_router(theme.router, prefix="/api/theme", tags=["Themes"])
app.include_router(rating_comments.router, prefix="/api/rating_comments", tags=["RatingComments"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["Favorites"])