from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from auth import create_access_token, verify_password
from app.deps import PluginManagerState
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
async def login(
    plugin_manager: PluginManagerState,
    form_data: OAuth2PasswordRequestForm = Depends(),
):

    async with plugin_manager.dao.session_factory() as session:
        result = await session.execute(select(User).where(User.username == form_data.username))
        user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect credentials")

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        roles=frozenset(user.roles),
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
    }
