from buraq import models


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
