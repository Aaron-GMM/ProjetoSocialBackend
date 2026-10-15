from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, users
from src.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API do projeto Caça Placa",
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
