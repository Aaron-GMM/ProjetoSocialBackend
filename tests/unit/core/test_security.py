from datetime import datetime, timedelta, timezone

from jose import jwt

from src.core.config import settings
from src.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_reset_token,
    generate_random_password,
    get_password_hash,
    verify_password,
)


def test_password_hash_and_verification():
    raw_password = "senha_teste_123"
    hashed = get_password_hash(raw_password)

    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("senha_incorreta", hashed) is False


def test_create_access_token_default_expiry():
    data = {"sub": "1", "role": "admin"}
    token = create_access_token(data=data)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "1"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_create_access_token_custom_expiry():
    data = {"sub": "2", "role": "user"}
    custom_delta = timedelta(minutes=15)
    token = create_access_token(data=data, expires_delta=custom_delta)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "2"
    assert payload["role"] == "user"
    assert "exp" in payload


def test_generate_random_password_meets_strength_requirements():
    for _ in range(20):
        password = generate_random_password()
        assert len(password) >= 5
        assert " " not in password
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)


def test_generate_random_password_is_unique():
    passwords = {generate_random_password() for _ in range(20)}
    assert len(passwords) == 20


def test_generate_random_password_custom_length():
    assert len(generate_random_password(length=20)) == 20


def test_create_reset_token_contains_reset_claim():
    token = create_reset_token(user_id=42)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["reset_token"] is True


def test_create_reset_token_expires_in_15_minutes():
    before = datetime.now(timezone.utc)
    token = create_reset_token(user_id=1)
    after = datetime.now(timezone.utc)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    tolerance = timedelta(seconds=2)
    expected_delta = timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    assert before + expected_delta - tolerance <= expires_at
    assert expires_at <= after + expected_delta + tolerance
