from fastapi import APIRouter, Depends
from sqlmodel import Session

# from src.infrastructure.database.connection import get_session

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login")
def login(db: Session = Depends()):  # TODO Equipe: Importar get_session
    """
    Recebe email/senha e retorna o JWT.
    Fluxo:
    1. Chama functions.user.get_user_by_email
    2. Usa core.security.verify_password
    3. Retorna core.security.create_access_token
    """
    pass  # TODO Equipe: Implementar o fluxo
