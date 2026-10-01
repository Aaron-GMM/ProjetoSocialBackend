from fastapi import HTTPException, status


class CacaPlacaException(HTTPException):
    """Classe base. Todos os erros do sistema vão herdar daqui."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


# Exemplo para a equipe copiar:
class UserNotFoundError(CacaPlacaException):
    def __init__(self):
        super().__init__(
            detail="Usuário não encontrado.", status_code=status.HTTP_404_NOT_FOUND
        )


# TODO Equipe: Criar TokenInvalidoException, PermissaoNegadaException, etc.
