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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

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

    # Geocodificação reversa (Nominatim / OpenStreetMap)
    # A política de uso do Nominatim exige um User-Agent identificável e limita
    # o uso a ~1 requisição/segundo: https://operations.osmfoundation.org/policies/nominatim/
    GEOCODING_URL: str = "https://nominatim.openstreetmap.org/reverse"
    GEOCODING_TIMEOUT: float = 3.0
    GEOCODING_USER_AGENT: str = "CacaPlacaAPI/0.1 (Projeto Social Quixada)"

    # Geocodificação local (base CNEFE/IBGE):
    # - até RAIO_M do endereço mais próximo: rua, bairro e CEP vêm da base;
    # - até RAIO_BAIRRO_M: só o bairro vem da base (rua vem do Nominatim);
    # - VIZINHOS: quantidade de endereços usados na votação do bairro.
    GEOCODING_LOCAL_RAIO_M: float = 150.0
    GEOCODING_LOCAL_RAIO_BAIRRO_M: float = 500.0
    GEOCODING_LOCAL_VIZINHOS: int = 7
    # Raio para padronizar um nome de rua (Nominatim ou digitado pelo agente)
    # com a grafia oficial da mesma rua no IBGE.
    GEOCODING_PADRONIZACAO_RAIO_M: float = 300.0


settings = Settings()
