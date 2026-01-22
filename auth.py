from dataclasses import dataclass
from fastapi import Request, HTTPException, Depends
from fastapi.security import (
    OAuth2PasswordBearer,
)
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from schemas import settings


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


@dataclass(frozen=True)
class UserContext:
    id: int
    roles: frozenset[str]
    username: str = ""


def create_access_token(
    *,
    user_id: int,
    username: str,
    roles: frozenset[str],
    expires_delta: timedelta | None = None,
) -> str:

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": username,
        "uid": user_id,
        "roles": list(roles),
        "exp": expire,
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def require_auth(
    request: Request,
    token: str = Depends(oauth2_scheme),
):
    payload = jwt.decode(token, settings.secret_key, algorithms=ALGORITHM)
    user_id = payload.get("uid")

    if user_id is None:
        raise HTTPException(status_code=401)

    request.state.user = UserContext(
        id=user_id,
        username=payload["sub"],
        roles=frozenset(payload["roles"]),
    )


def get_user(request: Request) -> UserContext:
    return request.state.user
