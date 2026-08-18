"""
Application configuration for ``buraq.contrib.auth``.

Add it to ``INSTALLED_APPS`` so model permissions are created automatically
after ``migrate``::

    INSTALLED_APPS = [
        "buraq.contrib.auth.apps.AuthConfig",
        ...
    ]

Listing the plain module path (``"buraq.contrib.auth"``) still works, but then
nothing connects the ``post_migrate`` receiver and permissions must be created
by calling ``create_permissions()`` yourself.
"""

from buraq.apps import AppConfig


class AuthConfig(AppConfig):
    name = "buraq.contrib.auth"
    label = "auth"
    verbose_name = "Authentication"

    async def ready(self) -> None:
        from buraq.contrib.auth import permissions

        permissions.register()
