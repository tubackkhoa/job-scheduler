from dataclasses import dataclass
from fastapi import Request, HTTPException, Depends
from fastapi.security import (
    OAuth2PasswordBearer,
)
from datetime import datetime, timedelta, timezone
from jose import ExpiredSignatureError, JWTError, jwt
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


@dataclass(frozen=True)
class UserContext:
    id: int
    roles: frozenset[str]
    username: str = ""


def create_access_token(
    *,
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "uid": user_id,
        "exp": expire,
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def require_auth(
    request: Request,
    token: str = Depends(oauth2_scheme),
):
    if not token:
        return

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # get back roles from cache
    request.state.uid = payload.get("uid")
