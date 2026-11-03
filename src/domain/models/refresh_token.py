from datetime import datetime, timezone

from sqlmodel import Column, DateTime, Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(index=True, nullable=False, unique=True)
    user_id: int = Field(
        foreign_key="users.id", index=True, nullable=False, ondelete="CASCADE"
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    revoked: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
