from fastapi import APIRouter, Depends
from sqlmodel import Session

# from src.infrastructure.database.connection import get_session

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/")
def list_users(db: Session = Depends()):  # TODO Equipe: Importar get_session
    """
    Retorna a lista de usuários. (Apenas ADMs)
    """
    pass  # TODO Equipe: Implementar o fluxo usando functions.user


@router.patch("/{user_id}")
def update_user(user_id: str, db: Session = Depends()):
    """
    Atualiza dados do usuário. (Apenas ADMs)
    """
    pass  # TODO Equipe: Implementar o fluxo
