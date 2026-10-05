from pydantic import BaseModel, Field


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
