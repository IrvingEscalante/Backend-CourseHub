from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

#Crea el motor con la url de MySql
engine = create_engine(settings.DATABASE_URL, future = True, echo=True)
Base = declarative_base()

#sersion local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base for the models


#Dependencia para usar en endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
