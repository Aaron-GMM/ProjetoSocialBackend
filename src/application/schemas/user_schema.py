from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from src.domain.enums.role import Role


class UserResponse(BaseModel):
    """Schema de resposta para usuário (sem password)."""

    id: int
    nome: str
    email: EmailStr
    role: Role
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Schema de atualização de usuário (PATCH)."""

    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
