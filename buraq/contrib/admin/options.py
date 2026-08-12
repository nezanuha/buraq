

class ModelAdmin:
    list_display: list[str] = []
    list_filter: list[str] = []
    search_fields: list[str] = []
    list_per_page: int = 20
    ordering: list[str] = []
    readonly_fields: list[str] = []
    fields: list[str] | None = None
    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True

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

    def get_fields(self) -> list[str]:
        if self.fields is not None:
            return self.fields
        return [n for n in self._all_column_names() if n != "id"]
