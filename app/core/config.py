from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 3000
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    CLOUD_NAME:str
    FRONTEND_URL:str
    API_KEY_CLOUDINARY:str
    API_SECRET_CLOUDINARY:str
    GEMINI_API_KEY:str

    class Config:
        env_file = ".env"


settings = Settings()