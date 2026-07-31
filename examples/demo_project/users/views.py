from fastapi import Depends, HTTPException
from buraq.core.auth import get_current_user_id
from .models import Profile
from .schemas import ProfileRead, ProfileUpdate


async def get_profile(user_id: int = Depends(get_current_user_id)) -> ProfileRead:
    profile = await Profile.objects.get_or_none(user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


async def update_profile(
    data: ProfileUpdate,
    user_id: int = Depends(get_current_user_id),
) -> ProfileRead:
    profile, created = await Profile.objects.get_or_create(
        defaults={"bio": "", "avatar_url": ""},
        user_id=user_id,
    )
    return await Profile.objects.update(profile.id, **data.model_dump(exclude_none=True))
