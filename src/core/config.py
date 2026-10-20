from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Caça Placa API"
    VERSION: str = "0.1.0"
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    RESET_TOKEN_EXPIRE_MINUTES: int

    # Frontend (usado para montar links enviados por e-mail e regras de CORS)
    FRONTEND_URL: str

    # SMTP (Gmail)
    MAIL_SERVER: str
    MAIL_PORT: int
    EMAIL: str
    EMAIL_PASSWORD: str

    # MinIO / Object Storage
    MINIO_ENDPOINT: str
    MINIO_PUBLIC_URL: str
    MINIO_APP_ACCESS_KEY: str
    MINIO_APP_SECRET_KEY: str
    MINIO_BUCKET_NAME: str
    MINIO_SECURE: bool


settings = Settings()
