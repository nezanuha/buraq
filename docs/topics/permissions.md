# Permissions & Groups

Buraq has a built-in permissions system with per-user and group-based permissions.

## Models

```python
from buraq.contrib.auth.models import Permission, Group, User
```

### Permission

A permission is a codename string, optionally scoped to an app (content type).

```python
# Create a permission
perm = await Permission.objects.create(
    name="Can publish posts",
    codename="publish_post",
    content_type="blog",
)
```

### Group

A named collection of permissions.

```python
# Create a group and assign a permission
editors = await Group.objects.create(name="Editors")
```

## Checking permissions

### On a user object

```python
user = await User.objects.get(id=1)

# Single permission
can_publish = await user.has_perm("publish_post")

# All of a list
can_edit_all = await user.has_perms(["edit_post", "delete_post"])

# Any permission in an app
has_blog_access = await user.has_module_perms("blog")
```

Superusers (`is_superuser=True`) always return `True` from all `has_perm*` methods.

Permission results are **cached** on the user instance after the first call.
Repeated `has_perm()` calls within the same request do not re-query the
database.  If you assign or revoke permissions at runtime and need the user
object to reflect the change immediately, call `_invalidate_perm_cache()`:

```python
await UserPermission.objects.create(user_id=user.id, permission_id=perm.id)
user._invalidate_perm_cache()   # clear cached set so next has_perm() re-fetches
```

### Permission.user_perm_str

`Permission` instances expose a `user_perm_str` read-only property that returns the formatted permission string ready for use with `has_perm()`:

```python
perm = await Permission.objects.get(codename="publish_post")
perm.user_perm_str  # → "blog.publish_post"

await user.has_perm(perm.user_perm_str)  # → True / False
```

The format is `"<app_label>.<codename>"`, where `app_label` is derived from `Permission.content_type`. If `content_type` is unset, `"buraq"` is used as the app label.

### In a view

```python
from buraq.decorators import permission_required

@permission_required("blog.publish_post")
async def publish_view(request, pk: int):
    ...
```

Or with CBV mixins:

```python
from buraq.views.mixins import PermissionRequiredMixin

class PublishView(PermissionRequiredMixin, UpdateView):
    model = Post
    permission_required = "blog.publish_post"
```

## Assigning permissions to users

```python
from buraq.contrib.auth.models import UserPermission

await UserPermission.objects.create(user_id=user.id, permission_id=perm.id)
```

## Assigning users to groups

```python
from buraq.contrib.auth.models import UserGroup

await UserGroup.objects.create(user_id=user.id, group_id=editors.id)
```

## Listing user permissions

```python
# Direct permissions
perms = await user.user_permissions()

# Groups
groups = await user.groups()
```

## Password utilities

```python
from buraq.contrib.auth import make_password, check_password, validate_password

# Hash a password
hashed = make_password("my-secret")

# Verify
ok = check_password("my-secret", hashed)

# Validate strength (raises ValidationError on failure)
validate_password("short")          # → ValidationError: too short
validate_password("12345678")       # → ValidationError: entirely numeric
validate_password("str0ng-pass")    # → OK

# Keep session alive after password change
from buraq.contrib.auth import update_session_auth_hash
await update_session_auth_hash(request, user)
```
