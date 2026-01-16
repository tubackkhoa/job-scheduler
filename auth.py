from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBasicCredentials, HTTPBasic
from datetime import datetime, timedelta
from typing import Set
import secrets
from jose import jwt

from enforcer import dataclass

SYSTEM_ROLES = {"admin"}


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password: str
    roles: set[str]


USERS: list[User] = [
    User(
        1,
        "thanhtu",
        "admin",
        {"admin"},
    ),
    User(
        2,
        "cuongnv",
        "admin",
        {"user"},
    ),
]

PUBLIC_PATHS = {
    "/login",
    "/health",
}

security = HTTPBasic()


def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
):
    if request.url.path in PUBLIC_PATHS:
        return None

    user = next((u for u in USERS if u.username == credentials.username), None)
    if not user or not secrets.compare_digest(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # attach user to request
    request.state.user = user


def get_user(request: Request) -> User:
    return request.state.user
