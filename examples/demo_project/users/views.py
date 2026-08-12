from fastapi import Depends, HTTPException

from buraq.contrib.auth import get_user
from .models import Profile
from .schemas import ProfileRead, ProfileUpdate


async def get_profile(request) -> ProfileRead:
    profile = await Profile.objects.get_or_none(user_id=request.user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


async def update_profile(request, data: ProfileUpdate) -> ProfileRead:
    profile, created = await Profile.objects.get_or_create(
        defaults={"bio": "", "avatar_url": ""},
        user_id=request.user.id,
    )
    return await Profile.objects.update(profile.id, **data.model_dump(exclude_none=True))
