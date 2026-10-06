from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.domain.enums.role import Role


class UserResponse(BaseModel):
    """Schema de resposta para usuário (sem password)."""

    id: int = Field(..., description="ID numérico único do usuário", examples=[1])
    nome: str = Field(..., description="Nome completo", examples=["João da Silva"])
    email: EmailStr = Field(
        ..., description="Endereço de e-mail", examples=["joao@exemplo.com"]
    )
    role: Role = Field(
        ...,
        description="Nível de acesso (AGENTE ou ADMINISTRADOR)",
        examples=["AGENTE"],
    )
    is_active: bool = Field(
        ..., description="Informa se a conta está ativa", examples=[True]
    )

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Schema de criação de usuário pelo admin (a senha é gerada pelo backend)."""

    nome: str = Field(
        ..., min_length=1, description="Nome completo", examples=["João da Silva"]
    )
    email: EmailStr = Field(
        ..., description="E-mail do novo usuário", examples=["joao@exemplo.com"]
    )


class UserUpdate(BaseModel):
    """Schema de atualização de usuário (PATCH)."""

    nome: Optional[str] = Field(None, description="Novo nome", examples=["João Silva"])
    email: Optional[EmailStr] = Field(
        None, description="Novo e-mail", examples=["novo.email@exemplo.com"]
    )
    role: Optional[Role] = Field(
        None, description="Novo nível de acesso", examples=["ADMINISTRADOR"]
    )
    is_active: Optional[bool] = Field(
        None,
        description="Se False, desativa a conta do usuário",
        examples=[False],
    )


class UserUpdateMe(BaseModel):
    """Schema de atualização do próprio usuário (PATCH /users/me)."""

    nome: Optional[str] = Field(
        None, description="Seu novo nome", examples=["Aaron Gibran"]
    )
    email: Optional[EmailStr] = Field(
        None, description="Seu novo e-mail", examples=["aaron@exemplo.com"]
    )
