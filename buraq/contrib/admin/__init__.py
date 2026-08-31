from buraq.contrib.admin.options import ModelAdmin
from buraq.contrib.admin.site import AdminSite, site

__all__ = ["ModelAdmin", "AdminSite", "site", "register"]


def register(*models, site=site):
    """Register a ``ModelAdmin`` for one or more models, as a decorator.

    The same thing ``site.register()`` does, written where the class is rather
    than in a call underneath it::

        from buraq.contrib import admin

        @admin.register(Post)
        class PostAdmin(admin.ModelAdmin):
            list_display = ("id", "title")

    This did not exist, which was easy to miss because it is the form most
    people reach for first: the scaffolded ``admin.py`` used it, so every
    generated app raised ``AttributeError`` on import.
    """
    from buraq.contrib.admin.site import AdminSite

    if not models:
        raise ValueError("admin.register() needs at least one model.")
    if not isinstance(site, AdminSite):
        raise TypeError("admin.register(site=...) takes an AdminSite.")

    def decorator(admin_class):
        if not issubclass(admin_class, ModelAdmin):
            raise TypeError(
                f"{admin_class.__name__} must subclass ModelAdmin to be registered."
            )
        for model in models:
            site.register(model, admin_class)
        return admin_class

    return decorator
