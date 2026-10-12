from fastapi import APIRouter, Depends

from app.api.deps import CurrentOwner, DbSession
from app.core.rate_limit import login_limiter
from app.core.security import create_access_token
from app.db.models import Owner
from app.schemas.auth import LoginRequest, OwnerRead, TokenResponse
from app.services import owners

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Rate-limited per IP: slows password guessing to a crawl.
@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
def login(data: LoginRequest, db: DbSession) -> TokenResponse:
    """Exchange the owner's email and password for an access token."""
    owner = owners.authenticate(db, data.email, data.password)
    token, expires_in = create_access_token(owner.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=OwnerRead)
def me(owner: CurrentOwner) -> Owner:
    """Who the token belongs to; the dashboard uses this to check a stored token."""
    return owner
