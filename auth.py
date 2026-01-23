from dataclasses import dataclass
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBasicCredentials, HTTPBasic
from datetime import datetime, timedelta
from typing import Optional, Set
import secrets


@dataclass(frozen=True)
class User:
    id: int
    roles: frozenset[str]
    username: str = ""


@dataclass(frozen=True)
class UserData:
    user: User
    password: str


USERS: list[UserData] = [
    UserData(
        User(1, frozenset({"admin"}), "thanhtu"),
        "admin",
    ),
    UserData(
        User(
            2,
            frozenset({"user"}),
            "cuongnv",
        ),
        "admin",
    ),
]


security = HTTPBasic(auto_error=False)


def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    # If no credentials provided, default to admin user
    if credentials is None:
        request.state.user = User(1, frozenset({"admin"}))
        return

    user = next((u for u in USERS if u.user.username == credentials.username), None)
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
