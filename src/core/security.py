# TODO Equipe: Importar as bibliotecas necessárias para JWT e Bcrypt (jose, passlib)

SECRET_KEY = "colocar-isso-em-um-arquivo-.env-depois"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano bate com o hash."""
    pass  # TODO Equipe: Implementar


def get_password_hash(password: str) -> str:
    """Gera o hash Bcrypt da senha."""
    pass  # TODO Equipe: Implementar


def create_access_token(data: dict) -> str:
    """Gera o token JWT."""
    pass  # TODO Equipe: Implementar
