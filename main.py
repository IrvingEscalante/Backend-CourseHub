from fastapi import FastAPI
from app.api.routes import auth
from app.db.session import Base, engine
from app.api.routes import users
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import course
import app.models 
#Crear tablas en mysql si no existen
Base.metadata.create_all(bind=engine)
app=FastAPI(title="Mi api")
origins = [
    "http://localhost:5173",  # tu frontend Angular
    "http://localhost:4200"  # opcional
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