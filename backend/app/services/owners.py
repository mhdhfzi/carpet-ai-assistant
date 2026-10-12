"""Owner accounts for the dashboard."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import AuthError, hash_password, verify_password
from app.db.models import Owner
from app.services.errors import ConflictError

MIN_PASSWORD_LENGTH = 10


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> Owner:
    """The owner with these credentials. One generic error for a wrong email or a wrong
    password, so the response doesn't reveal which emails have accounts."""
    owner = db.scalar(select(Owner).where(Owner.email == normalize_email(email)))
    if not verify_password(password, owner.password_hash if owner else None) or owner is None:
        raise AuthError("Incorrect email or password")
    return owner


def create_owner(db: Session, email: str, name: str, password: str) -> Owner:
    email = normalize_email(email)
    if "@" not in email:
        raise ValueError("Enter a valid email address")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if db.scalar(select(Owner.id).where(Owner.email == email)):
        raise ConflictError(f"An owner with email {email} already exists")
    owner = Owner(email=email, name=name.strip(), password_hash=hash_password(password))
    db.add(owner)
    db.commit()
    return owner
