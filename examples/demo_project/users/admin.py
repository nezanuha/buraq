from buraq.contrib.admin import ModelAdmin
from .models import Profile


class ProfileAdmin(ModelAdmin, model=Profile):
    column_list = [Profile.id, Profile.user_id, Profile.bio]
    column_searchable_list = [Profile.bio]
    name = "Profile"
    name_plural = "Profiles"
    icon = "fa-solid fa-user"
