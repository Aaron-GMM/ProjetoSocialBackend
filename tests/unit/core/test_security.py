from datetime import timedelta

from jose import jwt

from src.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
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
