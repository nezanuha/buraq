from buraq.urls import get, post

from . import views

# prefix is used when auto-discovered via INSTALLED_APPS
prefix = "/auth"

urlpatterns = [
    post("/register", views.register, name="auth_register", status_code=201),
    post("/token",    views.obtain_auth_token, name="auth_login"),
    get("/me",        views.get_me,   name="auth_me"),
]
