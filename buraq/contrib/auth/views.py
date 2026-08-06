from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status

from buraq.core.auth import create_access_token, get_current_user_id, hash_password, verify_password

from .models import User
from .schemas import LoginRequest, TokenResponse, UserCreate, UserRead


async def register(payload: UserCreate) -> UserRead:
    from sqlalchemy.exc import IntegrityError
    try:
        return await User.objects.create(
            email=payload.email,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            hashed_password=hash_password(payload.password),
        )
    except IntegrityError as exc:
        msg = str(exc).lower()
        if "email" in msg:
            raise HTTPException(status_code=400, detail="Email already registered") from exc
        if "username" in msg:
            raise HTTPException(status_code=400, detail="Username already taken") from exc
        raise HTTPException(status_code=400, detail="Registration failed due to a conflict.") from exc


async def login(payload: LoginRequest) -> TokenResponse:
    user = await User.objects.get_or_none(username=payload.username)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    await User.objects.update(user.id, last_login=datetime.now(UTC))
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


async def get_me(user_id: int = Depends(get_current_user_id)) -> UserRead:
    user = await User.objects.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
