from dataclasses import dataclass
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBasicCredentials, HTTPBasic
from datetime import datetime, timedelta
from typing import Set
import secrets


@dataclass(frozen=True)
class User:
    id: int
    roles: frozenset[str]


@dataclass(frozen=True)
class UserData:
    user: User
    username: str
    password: str


USERS: list[UserData] = [
    UserData(
        User(1, frozenset({"admin"})),
        "thanhtu",
        "admin",
    ),
    UserData(
        User(2, frozenset({"user"})),
        "cuongnv",
        "admin",
    ),
]


security = HTTPBasic()


def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
):

    user = next((u for u in USERS if u.username == credentials.username), None)
    if not user or not secrets.compare_digest(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # attach user to request
    request.state.user = user.user


def get_user(request: Request) -> User:
    return request.state.user
