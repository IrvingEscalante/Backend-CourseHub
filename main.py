from fastapi import FastAPI
from app.api.routes import auth
from app.db.session import Base, engine
from app.models.auth import user

#Crear tablas en mysql si no existen
Base.metadata.create_all(bind=engine)
app=FastAPI(title="Mi api")

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
