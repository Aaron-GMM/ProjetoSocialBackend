from pydantic import BaseModel, EmailStr, Field, field_validator


class TokenResponse(BaseModel):
    """Schema de resposta contendo o Token de Acesso JWT."""

    access_token: str = Field(
        ...,
        description=(
            "Token JWT (JSON Web Token) a ser enviado no Header "
            "'Authorization: Bearer <token>'"
        ),
        examples=["eyJhbGciOiJIUzI1NiIsInR..."],
    )
    refresh_token: str
    token_type: str = Field(
        "bearer", description="Tipo do token (geralmente bearer)", examples=["bearer"]
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Schema de requisição para solicitar redefinição de senha."""

    email: EmailStr = Field(
        ...,
        description="E-mail da conta a ser recuperada",
        examples=["joao@exemplo.com"],
    )


class ForgotPasswordResponse(BaseModel):
    """Schema de resposta genérica do forgot-password (prevenção a user enumeration)."""

    message: str = Field(..., description="Mensagem de confirmação genérica")


class ResetPasswordRequest(BaseModel):
    """Dados necessários para definir uma nova senha."""

    new_password: str = Field(
        ...,
        min_length=5,
        description="Nova senha do usuário",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if any(c.isspace() for c in v):
            raise ValueError("A senha não pode conter espaços.")
        return v
