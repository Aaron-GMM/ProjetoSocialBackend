from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Caça Placa API"
    VERSION: str = "0.1.0"
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Frontend (usado para montar links enviados por e-mail e regras de CORS)
    FRONTEND_URL: str

    # SMTP (Gmail)
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    EMAIL: str = ""
    EMAIL_PASSWORD: str = ""

    # MinIO / Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"
    MINIO_APP_ACCESS_KEY: str = ""
    MINIO_APP_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = "cacaplaca-images"
    MINIO_SECURE: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
