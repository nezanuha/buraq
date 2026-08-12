from buraq import models


def get_user_model():
    """
    Return the active user model — respects AUTH_USER_MODEL setting.

    Usage::

        from buraq.contrib.auth.models import get_user_model

        User = get_user_model()
        user = await User.objects.get(pk=1)
    """
    try:
        from buraq.conf import settings
        auth_model = getattr(settings, "AUTH_USER_MODEL", None)
    except Exception:
        auth_model = None

    if not auth_model:
        return User  # default concrete model

    from buraq.utils.module_loading import import_string
    try:
        return import_string(auth_model)
    except ImportError:
        # Try dotted app.ModelName style
        parts = auth_model.rsplit(".", 1)
        if len(parts) == 2:
            return import_string(f"{parts[0]}.models.{parts[1]}")
        return User


class PermissionsMixin:
    """
    Composable mixin that adds group/permission methods to a custom user model.

    Mix into your AbstractBaseUser subclass::

        class MyUser(AbstractBaseUser, PermissionsMixin):
            ...
    """

    is_superuser: bool = False

    async def _get_all_permission_codenames(self) -> set:
        if hasattr(self, "_perm_cache"):
            return self._perm_cache
        ups = await UserPermission.objects.filter(user_id=self.pk).all()
        perm_ids = {up.permission_id for up in ups}
        ugs = await UserGroup.objects.filter(user_id=self.pk).all()
        group_ids = [ug.group_id for ug in ugs]
        if group_ids:
            gps = await GroupPermission.objects.filter(group_id__in=group_ids).all()
            perm_ids |= {gp.permission_id for gp in gps}
        if not perm_ids:
            self._perm_cache: set = set()
            return self._perm_cache
        perms = await Permission.objects.filter(id__in=list(perm_ids)).all()
        self._perm_cache = {p.codename for p in perms}
        return self._perm_cache

    def _invalidate_perm_cache(self) -> None:
        self.__dict__.pop("_perm_cache", None)

    async def has_perm(self, perm: str) -> bool:
        if self.is_superuser:
            return True
        return perm in await self._get_all_permission_codenames()

    async def has_perms(self, perms) -> bool:
        if self.is_superuser:
            return True
        user_perms = await self._get_all_permission_codenames()
        return all(p in user_perms for p in perms)

    async def has_module_perms(self, app_label: str) -> bool:
        if self.is_superuser:
            return True
        user_perms = await self._get_all_permission_codenames()
        return any(p.startswith(f"{app_label}.") for p in user_perms)


class AbstractBaseUser(models.Model):
    """
    Abstract base for custom user models.

    Subclass this and define ``USERNAME_FIELD``, ``REQUIRED_FIELDS``, and
    ``EMAIL_FIELD`` as needed::

        class MyUser(AbstractBaseUser, PermissionsMixin):
            email    = models.EmailField(unique=True)
            is_staff = models.BooleanField(default=False)

            USERNAME_FIELD  = "email"
            REQUIRED_FIELDS = []

            class Meta:
                abstract = True
    """

    __abstract__ = True

    hashed_password = models.CharField(max_length=255)
    last_login = models.DateTimeField(null=True)

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list = []

    is_authenticated = True
    is_anonymous = False

    def get_username(self):
        return getattr(self, self.USERNAME_FIELD, "")

    async def set_password(self, raw_password: str) -> None:
        from buraq.contrib.auth import make_password
        self.hashed_password = await make_password(raw_password)

    async def check_password(self, raw_password: str) -> bool:
        from buraq.contrib.auth import check_password
        return await check_password(raw_password, self.hashed_password)

    @classmethod
    def get_email_field_name(cls) -> str:
        return cls.EMAIL_FIELD

    async def get_session_auth_hash(self) -> str:
        import hashlib

        from buraq.conf import settings
        key = getattr(settings, "SECRET_KEY", "")
        return hashlib.sha256(f"{key}{self.hashed_password}".encode()).hexdigest()[:8]


class AbstractUser(AbstractBaseUser, PermissionsMixin):
    """
    A fully featured user model with admin-compatible permissions.

    Extend this if you need to add fields to the built-in user::

        class MyUser(AbstractUser):
            bio = models.TextField(blank=True)

            class Meta:
                table_name = "myapp_users"
    """

    __abstract__ = True

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    first_name = models.CharField(max_length=150, null=True)
    last_name = models.CharField(max_length=150, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username


class Permission(models.Model):
    """
    A specific action a user can perform on a model.

    Permissions follow the pattern ``"app.action_model"``, e.g. ``"blog.add_post"``.
    """

    name        = models.CharField(max_length=255)
    codename    = models.CharField(max_length=100, unique=True)
    content_type = models.CharField(max_length=100, null=True)

    class Meta:
        table_name = "buraq_permissions"

    def __str__(self):
        return self.codename

    @property
    def user_perm_str(self) -> str:
        """
        Return the string suitable for use with ``User.has_perm()``.

        Format: ``"<app_label>.<codename>"``

        Usage::

            perm = await Permission.objects.get(codename="add_post")
            user.has_perm(perm.user_perm_str)  # → "blog.add_post"
        """
        app_label = (self.content_type or "").split(".")[0] if self.content_type else "buraq"
        return f"{app_label}.{self.codename}"


class Group(models.Model):
    """A named collection of permissions that can be assigned to users."""

    name = models.CharField(max_length=150, unique=True)

    class Meta:
        table_name = "buraq_groups"

    def __str__(self):
        return self.name

    async def permissions(self):
        from buraq.contrib.auth.models import GroupPermission
        gps = await GroupPermission.objects.filter(group_id=self.id).all()
        perm_ids = [gp.permission_id for gp in gps]
        if not perm_ids:
            return []
        return await Permission.objects.filter(id__in=perm_ids).all()


class UserGroup(models.Model):
    """Association table between User and Group."""

    user_id  = models.ForeignKey("buraq_users", on_delete=models.CASCADE)
    group_id = models.ForeignKey("buraq_groups", on_delete=models.CASCADE)

    class Meta:
        table_name = "buraq_user_groups"


class UserPermission(models.Model):
    """Direct user-level permission assignment."""

    user_id       = models.ForeignKey("buraq_users", on_delete=models.CASCADE)
    permission_id = models.ForeignKey("buraq_permissions", on_delete=models.CASCADE)

    class Meta:
        table_name = "buraq_user_permissions"


class GroupPermission(models.Model):
    """Association table between Group and Permission."""

    group_id      = models.ForeignKey("buraq_groups", on_delete=models.CASCADE)
    permission_id = models.ForeignKey("buraq_permissions", on_delete=models.CASCADE)

    class Meta:
        table_name = "buraq_group_permissions"


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

    async def check_password(self, raw_password: str) -> bool:
        from buraq.contrib.auth import check_password
        return await check_password(raw_password, self.hashed_password)

    async def set_password(self, raw_password: str) -> None:
        from buraq.contrib.auth import make_password
        self.hashed_password = await make_password(raw_password)

    async def _get_all_permission_codenames(self) -> set[str]:
        """Fetch all permission codenames for this user, cached on the instance."""
        if hasattr(self, "_perm_cache"):
            return self._perm_cache

        # Query 1 — direct permission IDs
        ups = await UserPermission.objects.filter(user_id=self.id).all()
        perm_ids = {up.permission_id for up in ups}

        # Query 2 — group permission IDs (single IN query across all groups)
        ugs = await UserGroup.objects.filter(user_id=self.id).all()
        group_ids = [ug.group_id for ug in ugs]
        if group_ids:
            gps = await GroupPermission.objects.filter(group_id__in=group_ids).all()
            perm_ids |= {gp.permission_id for gp in gps}

        if not perm_ids:
            self._perm_cache: set[str] = set()
            return self._perm_cache

        # Query 3 — fetch codenames for all collected IDs at once
        perms = await Permission.objects.filter(id__in=list(perm_ids)).all()
        self._perm_cache = {p.codename for p in perms}
        return self._perm_cache

    def _invalidate_perm_cache(self) -> None:
        """Call after changing a user's permissions to force a fresh fetch."""
        self.__dict__.pop("_perm_cache", None)

    async def has_perm(self, perm: str) -> bool:
        """Return True if the user has the given permission codename."""
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        return perm in await self._get_all_permission_codenames()

    async def has_perms(self, perms: list[str]) -> bool:
        """Return True if the user has all the given permissions (single batch query)."""
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        user_perms = await self._get_all_permission_codenames()
        return all(p in user_perms for p in perms)

    async def has_module_perms(self, app_label: str) -> bool:
        """Return True if the user has any permission for the given app."""
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        user_perms = await self._get_all_permission_codenames()
        return any(p.startswith(f"{app_label}.") for p in user_perms)

    async def groups(self):
        """Return all groups this user belongs to."""
        ugs = await UserGroup.objects.filter(user_id=self.id).all()
        group_ids = [ug.group_id for ug in ugs]
        if not group_ids:
            return []
        return await Group.objects.filter(id__in=group_ids).all()

    async def user_permissions(self):
        """Return all direct permissions for this user."""
        ups = await UserPermission.objects.filter(user_id=self.id).all()
        perm_ids = [up.permission_id for up in ups]
        if not perm_ids:
            return []
        return await Permission.objects.filter(id__in=perm_ids).all()
