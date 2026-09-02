

"""
What an admin class may say about a model.

``ModelAdmin`` is the whole of the admin's configuration surface, and two parts
of it are about who may see what rather than how it looks: ``get_queryset``
narrows the rows a request may reach at all, and the ``has_*_permission``
methods decide what may be done with them.
"""


class ModelAdmin:
    list_display: list[str] = []
    list_filter: list[str] = []
    search_fields: list[str] = []
    list_per_page: int = 20
    ordering: list[str] = []
    readonly_fields: list[str] = []
    fields: list[str] | None = None
    #: Fields grouped into titled sections, as
    #: ``[("Content", {"fields": [...]}), (None, {"fields": [...]})]``.
    fieldsets: list | None = None
    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True
    #: Bulk operations offered above the list. Method names on this class,
    #: or plain callables taking (modeladmin, request, queryset).
    actions: list = []

    def __init__(self, model: type, admin_site):
        self.model = model
        self.admin_site = admin_site

    def get_model_name(self) -> str:
        return self.model.__name__.lower()

    def get_verbose_name(self) -> str:
        return getattr(self.model, "_meta_verbose_name", None) or self.model.__name__

    def get_verbose_name_plural(self) -> str:
        return (
            getattr(self.model, "_meta_verbose_name_plural", None) or f"{self.get_verbose_name()}s"
        )

    def get_app_label(self) -> str:
        parts = [p for p in self.model.__module__.split(".") if p not in ("models", "")]
        return parts[-1] if parts else "unknown"

    def _all_columns(self) -> list:
        try:
            return list(self.model.__table__.columns)
        except Exception:
            return []

    def _all_column_names(self) -> list[str]:
        return [c.name for c in self._all_columns()]

    def get_list_display(self) -> list[str]:
        if self.list_display:
            return self.list_display
        names = self._all_column_names()
        return names[:6] if names else ["id"]

    def get_fieldsets(self, request, obj=None) -> list:
        """The form's sections, as ``(title, {"fields": [...]})`` pairs.

        Falls back to one untitled section holding :meth:`get_fields`, so a form
        renders the same whether or not an admin declares any -- the template
        has one shape to handle rather than two.

            fieldsets = [
                ("Content", {"fields": ["title", "body"]}),
                ("Publishing", {"fields": ["status", "published_at"],
                                "description": "Leave the date empty to keep it a draft."}),
            ]

        A title of ``None`` renders without a heading, which is how Django
        writes the first section of a form that has one unlabelled group.
        """
        if self.fieldsets is not None:
            return list(self.fieldsets)
        return [(None, {"fields": self.get_fields()})]

    def fieldset_fields(self, request, obj=None) -> list[str]:
        """Every field named across the sections, in order.

        What the form actually saves. Reading it from the sections rather than
        from ``fields`` keeps the two from disagreeing: a field left out of
        every section is not on the form, so it must not be written either.
        """
        names: list[str] = []
        for _title, options in self.get_fieldsets(request, obj):
            for name in options.get("fields", ()):
                if name not in names:
                    names.append(name)
        return names

    # ── Bulk actions ─────────────────────────────────────────────────────────

    async def delete_selected(self, request, queryset) -> str:
        """Delete every selected row. Offered unless delete is refused."""
        count = await queryset.count()
        await queryset.delete()
        return f"Deleted {count} {self.get_verbose_name_plural().lower()}."

    delete_selected.short_description = "Delete selected"

    async def get_actions(self, request) -> dict:
        """The actions this request may run, by name.

        Delete is included only when it is permitted, so a read-only admin does
        not offer a button that answers 403 -- which is a worse way to learn it
        than not seeing the button.
        """
        found: dict = {}
        if await self.has_delete_permission(request):
            found["delete_selected"] = self.delete_selected

        for action in self.actions:
            func = getattr(self, action, None) if isinstance(action, str) else action
            if func is None:
                raise AttributeError(
                    f"{type(self).__name__}.actions names {action!r}, which is "
                    f"not a method on it."
                )
            found[getattr(func, "__name__", str(action))] = func
        return found

    @staticmethod
    def action_label(func) -> str:
        """What the dropdown calls it: ``short_description``, else the name."""
        described = getattr(func, "short_description", None)
        if described:
            return described
        return getattr(func, "__name__", "action").replace("_", " ").capitalize()

    # ── Which rows a request may reach ───────────────────────────────────────

    def get_queryset(self, request):
        """The rows this request is allowed to work with.

        Everything the admin reads goes through here -- the list, and each of
        the fetches behind the change and delete pages. That last part is the
        point: narrowing only the list would hide rows while leaving
        ``/admin/app/model/41/change`` open to anyone who typed it.

        Scoping an admin to a tenant, or to what a user owns, is this method::

            def get_queryset(self, request):
                qs = super().get_queryset(request)
                user = request.scope["user"]
                if user.is_superuser:
                    return qs
                return qs.filter(owner_id=user.id)

        It returns a queryset rather than awaiting one, so filters and ordering
        can still be added before anything runs.
        """
        return self.model.objects.all()

    async def get_object(self, request, pk):
        """One row, if this request may reach it -- otherwise ``None``.

        Fetched through :meth:`get_queryset`, so a row outside the scope is not
        found rather than found and then refused. The two look the same to the
        visitor, and only one of them can leak that the row exists.
        """
        try:
            return await self.get_queryset(request).filter(id=pk).first()
        except Exception:
            return None

    # ── What may be done with them ───────────────────────────────────────────
    #
    # Async, unlike Django's: deciding whether someone may edit a row usually
    # means asking the database something -- what they own, which team they are
    # on -- and this framework has no way to do that from a synchronous method.
    # Each falls back to the can_* flags, so an admin that set those behaves as
    # it did before.

    async def has_module_permission(self, request) -> bool:
        """Whether this model appears in the admin at all."""
        return True

    async def has_view_permission(self, request, obj=None) -> bool:
        return True

    async def has_add_permission(self, request) -> bool:
        return self.can_create

    async def has_change_permission(self, request, obj=None) -> bool:
        """``obj`` is None when asking about the model rather than one row."""
        return self.can_edit

    async def has_delete_permission(self, request, obj=None) -> bool:
        return self.can_delete

    def get_fields(self) -> list[str]:
        if self.fields is not None:
            return self.fields
        return [n for n in self._all_column_names() if n != "id"]
