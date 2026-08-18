"""
Model metadata — the object behind ``Model._meta``.

Collects every ``class Meta`` option into one place so the rest of the ORM (and
contrib apps like admin and auth) can read model configuration from a single,
documented surface instead of scattered ``_meta_*`` class attributes.
"""

from __future__ import annotations

DEFAULT_NAMES = (
    "abstract",
    "app_label",
    "base_manager_name",
    "constraints",
    "db_table",
    "db_table_comment",
    "default_manager_name",
    "default_permissions",
    "default_related_name",
    "get_latest_by",
    "indexes",
    "managed",
    "order_with_respect_to",
    "ordering",
    "permissions",
    "proxy",
    "table_name",  # Buraq alias for db_table
    "unique_together",
    "verbose_name",
    "verbose_name_plural",
)

DEFAULT_PERMISSIONS = ("add", "change", "delete", "view")


def _camel_to_spaces(name: str) -> str:
    """``BlogPost`` -> ``blog post`` — the default verbose_name."""
    out = []
    for i, char in enumerate(name):
        if char.isupper() and i and not name[i - 1].isupper():
            out.append(" ")
        out.append(char.lower())
    return "".join(out)


def _derive_app_label(model_cls) -> str:
    """
    Infer the app label from the model's module.

    ``myshop.models`` -> ``myshop``; ``myshop.models.post`` -> ``myshop``.
    Declare ``Meta.app_label`` explicitly when a model lives outside an app.
    """
    parts = (model_cls.__module__ or "").split(".")
    if "models" in parts:
        idx = parts.index("models")
        if idx:
            return parts[idx - 1]
    return parts[-1] if parts else ""


class Options:
    """Resolved ``class Meta`` for a model. Available as ``Model._meta``."""

    def __init__(self, model_cls, meta=None):
        self.model = model_cls
        self.object_name = model_cls.__name__
        self.model_name = model_cls.__name__.lower()

        unknown = sorted(
            name
            for name in vars(meta or object)
            if not name.startswith("_") and name not in DEFAULT_NAMES
        )
        self.unknown_options = unknown
        if unknown:
            # Fail loudly instead of silently ignoring a typo such as `orderring`,
            # which would otherwise leave the model on default behaviour with no
            # indication anything was wrong.
            raise TypeError(
                f"{model_cls.__name__}: class Meta got invalid attribute(s): "
                + ", ".join(unknown)
            )

        get = lambda name, default=None: getattr(meta, name, default)  # noqa: E731

        # ── Identity ──────────────────────────────────────────────────────
        self.app_label = get("app_label") or _derive_app_label(model_cls)

        # ── Structure ─────────────────────────────────────────────────────
        # `abstract` and `proxy` are deliberately NOT inherited: a concrete
        # child of an abstract model must not itself become abstract, even when
        # it does `class Meta(Parent.Meta)`, so read these from the Meta's own
        # __dict__ rather than through the MRO.
        own = getattr(meta, "__dict__", {})
        self.abstract = bool(own.get("abstract", False))
        self.proxy = bool(own.get("proxy", False))
        self.managed = bool(get("managed", True))
        self.db_table = get("table_name") or get("db_table")
        self.db_table_comment = get("db_table_comment")

        # ── Query behaviour ───────────────────────────────────────────────
        self.ordering = list(get("ordering", []) or [])
        self.get_latest_by = get("get_latest_by")
        self.order_with_respect_to = get("order_with_respect_to")

        # ── Schema extras ─────────────────────────────────────────────────
        self.indexes = list(get("indexes", []) or [])
        self.constraints = list(get("constraints", []) or [])
        self.unique_together = list(get("unique_together", []) or [])

        # ── Managers ──────────────────────────────────────────────────────
        self.base_manager_name = get("base_manager_name")
        self.default_manager_name = get("default_manager_name")

        # ── Relations ─────────────────────────────────────────────────────
        self.default_related_name = get("default_related_name")

        # ── Permissions ───────────────────────────────────────────────────
        self.permissions = list(get("permissions", []) or [])
        default_perms = get("default_permissions", DEFAULT_PERMISSIONS)
        self.default_permissions = tuple(default_perms)

        # ── Human-readable names ──────────────────────────────────────────
        self.verbose_name = get("verbose_name") or _camel_to_spaces(model_cls.__name__)
        self.verbose_name_plural = get("verbose_name_plural") or f"{self.verbose_name}s"

        # Set once the table name is resolved by the metaclass.
        self.concrete_model = model_cls

    # ── Read-only attributes ──────────────────────────────────────────────

    @property
    def label(self) -> str:
        """``polls.Question``"""
        return f"{self.app_label}.{self.object_name}"

    @property
    def label_lower(self) -> str:
        """``polls.question``"""
        return f"{self.app_label}.{self.model_name}"

    @property
    def table_name(self) -> str | None:
        """Actual table this model reads/writes (a proxy shares its parent's)."""
        return getattr(self.concrete_model, "__tablename__", None)

    def get_default_permissions(self) -> list[tuple[str, str]]:
        """
        ``[(codename, name)]`` for this model — the automatic add/change/delete/
        view set plus anything declared in ``Meta.permissions``.
        """
        perms = [
            (f"{action}_{self.model_name}", f"Can {action} {self.verbose_name}")
            for action in self.default_permissions
        ]
        perms.extend(self.permissions)
        return perms

    def __repr__(self) -> str:
        return f"<Options for {self.label}>"
