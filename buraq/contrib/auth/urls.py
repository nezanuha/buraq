from buraq.urls import get, post

from . import views

urlpatterns = [
    post("/register", views.register,                  name="auth_register", status_code=201),
    get("/login",     views.LoginView.as_view(),        name="auth_login"),
    post("/login",    views.LoginView.as_view(),        name="auth_login_post"),
    get("/logout",    views.LogoutView.as_view(),       name="auth_logout"),
    post("/logout",   views.LogoutView.as_view(),       name="auth_logout_post"),
]
