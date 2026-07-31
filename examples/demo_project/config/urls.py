from buraq import Buraq
from buraq.urls import path, include
from buraq.contrib.admin import BuraqAdmin

app = Buraq(settings_module="config.settings")
admin = BuraqAdmin(app)

# ── URL Configuration ────────────────────────────────────────────────────────
urlpatterns = [
    path("/auth",  include("buraq.contrib.auth.urls")),
    path("/users", include("users.urls")),
]

app.load_urls(urlpatterns)


@app.get("/")
async def index():
    return {"message": "Welcome to Buraq!", "docs": "/api/docs"}
