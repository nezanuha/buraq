from buraq.urls import get, post

from . import views

# prefix is used when auto-discovered via INSTALLED_APPS
prefix = "/auth"

urlpatterns = [
    post("/register", views.register,                  name="auth_register", status_code=201),
    get("/login",     views.LoginView.as_view(),        name="auth_login"),
    post("/login",    views.LoginView.as_view(),        name="auth_login_post"),
    get("/logout",    views.LogoutView.as_view(),       name="auth_logout"),
    post("/logout",   views.LogoutView.as_view(),       name="auth_logout_post"),
]
