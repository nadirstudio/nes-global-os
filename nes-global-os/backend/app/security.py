"""Password hashing, session tokens, MFA (TOTP) and encryption of secrets at rest."""
from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pyotp
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

MIN_PASSWORD_LEN = 10


def validate_password_strength(pw: str) -> str | None:
    if len(pw) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    classes = sum([any(c.islower() for c in pw), any(c.isupper() for c in pw),
                   any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)])
    if classes < 3:
        return "Use at least three of: lowercase, uppercase, digits, symbols."
    return None


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


MOBILE_TTL_DAYS = 30


def create_token(user_id: uuid.UUID, role: str, token_version: int, mfa_passed: bool = True,
                 device_id: uuid.UUID | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = timedelta(days=MOBILE_TTL_DAYS) if device_id else timedelta(minutes=settings.jwt_ttl_minutes if mfa_passed else 5)
    payload = {
        "sub": str(user_id), "role": role, "tv": token_version, "mfa": mfa_passed,
        "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp()),
    }
    if device_id:
        payload["did"] = str(device_id)  # mobile sessions are bound to a revocable device
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_file_token(doc_id: uuid.UUID, user_id: uuid.UUID, minutes: int = 5) -> str:
    """Short-lived, single-document download link (for opening files in the phone's viewer)."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"doc": str(doc_id), "sub": str(user_id), "exp": int(exp.timestamp()), "typ": "file"},
                      settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------- secrets at rest
def _fernet() -> Fernet:
    key = settings.master_key
    if not key:
        if settings.env == "production":
            raise RuntimeError("NES_MASTER_KEY must be set in production")
        # Development fallback: derive from the JWT secret so local runs work.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def key_hint(value: str) -> str:
    return "…" + value[-4:] if len(value) >= 8 else "set"


# ---------------------------------------------------------------- MFA
def new_mfa_secret() -> str:
    return pyotp.random_base32()


def mfa_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="NES GLOBAL OS")


def verify_mfa(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
