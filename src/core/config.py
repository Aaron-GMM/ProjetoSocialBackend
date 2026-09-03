from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Caça Placa API"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/cacaplaca"

    class Config:
        env_file = ".env"

settings = Settings()
