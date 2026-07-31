from buraq.urls import get, put
from . import views

urlpatterns = [
    get("/profile",  views.get_profile,    name="user_profile"),
    put("/profile",  views.update_profile, name="user_profile_update"),
]
