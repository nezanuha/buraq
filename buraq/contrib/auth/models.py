from buraq import models


class AnonymousUser:
    """Represents an unauthenticated user."""
    id           = None
    pk           = None
    username     = ""
    is_active    = False
    is_staff     = False
    is_superuser = False
    is_authenticated = False

    def __str__(self):
        return "AnonymousUser"

    def __repr__(self):
        return "<AnonymousUser>"


class User(models.Model):
    email           = models.CharField(max_length=255, unique=True, db_index=True)
    username        = models.CharField(max_length=150, unique=True, db_index=True)
    first_name      = models.CharField(max_length=150, null=True)
    last_name       = models.CharField(max_length=150, null=True)
    hashed_password = models.CharField(max_length=255)
    is_active       = models.BooleanField(default=True)
    is_staff        = models.BooleanField(default=False)
    is_superuser    = models.BooleanField(default=False)
    date_joined     = models.DateTimeField(auto_now_add=True)
    last_login      = models.DateTimeField(null=True)

    class Meta:
        table_name = "buraq_users"

    is_authenticated = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username
