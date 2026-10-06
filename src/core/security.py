import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
RESET_TOKEN_EXPIRE_MINUTES = settings.RESET_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano bate com o hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera o hash Bcrypt da senha."""
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Gera o token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_random_password(length: int = 12) -> str:
    """Gera uma senha forte aleatória (letras e dígitos, sem espaços)."""
    alphabet = string.ascii_letters + string.digits
    # Garante ao menos um caractere de cada classe para a senha ser forte
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - len(password))]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def create_reset_token(user_id: int) -> str:
    """Gera um JWT de vida curta com a claim `reset_token` para redefinição de senha."""
    data = {"sub": str(user_id), "reset_token": True}
    expires_delta = timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    return create_access_token(data=data, expires_delta=expires_delta)


def validate_reset_token(token: str) -> Optional[int]:
    """Valida um token de redefinição e retorna o ID do usuário.

    Retorna ``None`` para tokens inválidos, expirados ou que não foram
    emitidos especificamente para redefinição de senha.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("reset_token") is not True:
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        return int(user_id)
    except (JWTError, TypeError, ValueError):
        return None
