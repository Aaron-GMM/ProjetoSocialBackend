from pydantic import BaseModel, EmailStr, Field


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
    token_type: str = Field(
        "bearer", description="Tipo do token (geralmente bearer)", examples=["bearer"]
    )


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
