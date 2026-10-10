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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
