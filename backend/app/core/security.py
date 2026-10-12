"""Password hashing and login tokens for the owner dashboard."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

# Argon2id with the library's defaults (OWASP's first recommendation): deliberately slow and
# memory-hungry, so a stolen hash is expensive to crack.
_hasher = PasswordHasher()

# Checked when the email doesn't exist, so a failed login takes the same time either way
# and response timings don't reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

ALGORITHM = "HS256"


class AuthError(Exception):
    pass


class ReadOnlyAccountError(Exception):
    """A logged-in account that may look but not change anything (the public demo): a 403."""


class AuthNotConfiguredError(Exception):
    """The server can't issue or check tokens (no JWT_SECRET): a 503, not a failed login."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(owner_id: int) -> tuple[str, int]:
    """A signed token proving who logged in. Returns (token, lifetime in seconds)."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_minutes)
    # Real time, not app.core.clock: PyJWT checks expiry against the real clock.
    now = datetime.now(UTC)
    claims = {"sub": str(owner_id), "iat": now, "exp": now + lifetime, "type": "access"}
    token = jwt.encode(claims, _secret(), algorithm=ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> int:
    """The owner id in a valid token. Raises AuthError if the token is forged, expired or
    malformed. The algorithm list is explicit, which blocks "alg: none" forgeries."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if claims.get("type") != "access":
            raise AuthError("Wrong token type")
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise AuthError("Invalid or expired token") from exc


def _secret() -> str:
    secret = get_settings().jwt_secret
    if secret is None:
        # Refuse rather than fall back to a guessable default secret.
        raise AuthNotConfiguredError("JWT_SECRET is not set; add it to backend/.env")
    return secret.get_secret_value()
