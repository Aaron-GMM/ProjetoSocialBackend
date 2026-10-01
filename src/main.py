from fastapi import FastAPI

from src.api.routes import auth, users
from src.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API do projeto Caça Placa",
    version=settings.VERSION,
)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
