"""
An admin scoped to a tenant has to stay scoped everywhere.

`get_queryset` narrowing only the list would hide rows on one page while
leaving `/admin/app/model/41/change` open to anyone who typed it -- and the
bulk-delete endpoint took ids straight from the request body, so a scoped admin
could still be asked to delete rows it was never allowed to see.

These check that every way in goes through the same queryset.
"""

import inspect

import pytest

from buraq.contrib.admin.options import ModelAdmin


class _Query:
    """A queryset that records what was filtered, without a database."""

    def __init__(self, rows, filters=None):
        self.rows = rows
        self.filters = filters or []

    def filter(self, *args, **kwargs):
        return _Query(
            [r for r in self.rows if all(r.get(k) == v for k, v in kwargs.items())],
            self.filters + [kwargs or args],
        )

    async def first(self):
        return self.rows[0] if self.rows else None

    async def count(self):
        return len(self.rows)

    async def delete(self):
        return len(self.rows)


class _Model:
    rows = [
        {"id": 1, "owner_id": 7, "title": "mine"},
        {"id": 2, "owner_id": 9, "title": "theirs"},
    ]

    class objects:
        @staticmethod
        def all():
            return _Query(list(_Model.rows))


class _Request:
    def __init__(self, owner_id):
        self.scope = {"user": type("U", (), {"id": owner_id})()}


class ScopedAdmin(ModelAdmin):
    """The documented shape of a tenant-scoped admin."""

    def get_queryset(self, request):
        return super().get_queryset(request).filter(owner_id=request.scope["user"].id)


@pytest.fixture
def admin():
    return ScopedAdmin(_Model, admin_site=None)


# --- get_queryset ------------------------------------------------------------


def test_the_default_queryset_is_everything(admin):
    plain = ModelAdmin(_Model, admin_site=None)
    assert len(plain.get_queryset(_Request(7)).rows) == 2


@pytest.mark.asyncio
async def test_a_scoped_admin_sees_only_its_own_rows(admin):
    assert await admin.get_queryset(_Request(7)).count() == 1


@pytest.mark.asyncio
async def test_get_object_honours_the_scope(admin):
    """The bypass this exists to close: the list can hide a row while the URL
    still reaches it."""
    assert await admin.get_object(_Request(7), 1) is not None
    assert await admin.get_object(_Request(7), 2) is None, "reached another owner's row"


@pytest.mark.asyncio
async def test_get_object_returns_none_rather_than_raising(admin):
    """Not found and not permitted look the same to the visitor, and only one
    of them can leak that the row exists."""
    assert await admin.get_object(_Request(7), 999) is None


# --- the permission methods --------------------------------------------------


@pytest.mark.asyncio
async def test_the_permissions_default_to_the_can_flags():
    """An admin that set can_create/can_edit/can_delete keeps behaving as it
    did -- these are a way to say more, not a change of default."""

    class Restricted(ModelAdmin):
        can_create = False
        can_edit = False
        can_delete = False

    admin = Restricted(_Model, admin_site=None)
    request = _Request(7)

    assert await admin.has_add_permission(request) is False
    assert await admin.has_change_permission(request) is False
    assert await admin.has_delete_permission(request) is False
    assert await admin.has_view_permission(request) is True


@pytest.mark.asyncio
async def test_a_permission_may_depend_on_the_row():
    """Which is the point of `obj` -- can_edit is a class-wide flag and cannot
    say "yours, but not theirs"."""

    class OwnerOnly(ModelAdmin):
        async def has_change_permission(self, request, obj=None):
            if obj is None:
                return True
            return obj["owner_id"] == request.scope["user"].id

    admin = OwnerOnly(_Model, admin_site=None)
    request = _Request(7)

    assert await admin.has_change_permission(request, _Model.rows[0]) is True
    assert await admin.has_change_permission(request, _Model.rows[1]) is False


@pytest.mark.parametrize(
    "name",
    [
        "has_module_permission",
        "has_view_permission",
        "has_add_permission",
        "has_change_permission",
        "has_delete_permission",
    ],
)
def test_every_permission_hook_is_async(name):
    """
    Unlike Django's. Deciding whether someone may edit a row usually means
    asking the database something -- what they own, which team they are on --
    and this framework has no way to do that from a synchronous method.
    """
    assert inspect.iscoroutinefunction(getattr(ModelAdmin, name))


def test_get_queryset_is_not_async():
    """It builds a query rather than running one, so the caller can still add
    filters, ordering and paging before anything executes."""
    assert not inspect.iscoroutinefunction(ModelAdmin.get_queryset)


# --- every way in ------------------------------------------------------------


def test_no_admin_view_reads_the_model_directly():
    """
    The guard on all of the above. Every read has to go through get_queryset or
    get_object; one `Model.objects.all()` left in a view is a scope that only
    mostly holds -- and the bulk delete was exactly that, taking ids from the
    request body and deleting them unfiltered.
    """
    import pathlib

    source = pathlib.Path("buraq/contrib/admin/views.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        if ("ma.model.objects" in line or "model.objects.count" in line)
        # Creating a row is not a read, and there is nothing to scope it
        # against -- the row does not exist yet. Setting an owner on it is the
        # admin class's business.
        and "objects.create(" not in line
    ]
    assert not offenders, f"reads around the scope: {offenders}"


# --- actions -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_selected_is_offered_when_delete_is_permitted(admin):
    assert "delete_selected" in await admin.get_actions(_Request(7))


@pytest.mark.asyncio
async def test_delete_selected_is_absent_when_delete_is_refused():
    """A read-only admin should not offer a button that answers 403 -- that is
    a worse way to learn it than not seeing the button."""

    class ReadOnly(ScopedAdmin):
        can_delete = False

    assert "delete_selected" not in await ReadOnly(_Model, None).get_actions(_Request(7))


@pytest.mark.asyncio
async def test_an_action_named_on_the_class_is_offered():
    class WithAction(ScopedAdmin):
        actions = ["publish"]

        async def publish(self, request, queryset):
            return f"Published {await queryset.count()}."

    actions = await WithAction(_Model, None).get_actions(_Request(7))
    assert "publish" in actions


@pytest.mark.asyncio
async def test_an_action_runs_against_the_selected_rows():
    seen = {}

    class WithAction(ScopedAdmin):
        actions = ["publish"]

        async def publish(self, request, queryset):
            seen["count"] = await queryset.count()
            return "done"

    admin = WithAction(_Model, None)
    actions = await admin.get_actions(_Request(7))
    assert await actions["publish"](_Request(7), _Query(_Model.rows[:1])) == "done"
    assert seen["count"] == 1


@pytest.mark.asyncio
async def test_an_action_that_does_not_exist_says_so_at_registration():
    """Rather than silently offering nothing, or failing when someone runs it."""

    class Broken(ScopedAdmin):
        actions = ["no_such_method"]

    with pytest.raises(AttributeError, match="not a method"):
        await Broken(_Model, None).get_actions(_Request(7))


def test_the_dropdown_label_prefers_short_description(admin):
    async def publish(self, request, queryset):
        return ""

    publish.short_description = "Publish the selected posts"
    assert admin.action_label(publish) == "Publish the selected posts"


def test_the_dropdown_label_falls_back_to_the_name(admin):
    async def mark_as_read(self, request, queryset):
        return ""

    assert admin.action_label(mark_as_read) == "Mark as read"


# --- fieldsets ---------------------------------------------------------------


class _Col:
    def __init__(self, name):
        self.name = name
        self.nullable = True
        self.default = None
        self.server_default = None
        self.primary_key = False
        self.type = type("T", (), {"__str__": lambda s: "VARCHAR"})()


class _FieldModel:
    __name__ = "Post"

    class __table__:
        columns = [_Col("id"), _Col("title"), _Col("body"), _Col("secret")]


def test_no_fieldsets_gives_one_untitled_section():
    """So the template has one shape to render, not two."""
    admin = ModelAdmin(_FieldModel, None)
    admin.fields = ["title", "body"]

    assert admin.get_fieldsets(None) == [(None, {"fields": ["title", "body"]})]


def test_fieldsets_are_returned_as_declared():
    class Grouped(ModelAdmin):
        fieldsets = [
            ("Content", {"fields": ["title", "body"]}),
            ("Meta", {"fields": ["secret"], "description": "Internal."}),
        ]

    sections = Grouped(_FieldModel, None).get_fieldsets(None)
    assert [title for title, _ in sections] == ["Content", "Meta"]
    assert sections[1][1]["description"] == "Internal."


def test_the_fields_on_the_form_come_from_the_sections():
    class Grouped(ModelAdmin):
        fieldsets = [
            ("Content", {"fields": ["title", "body"]}),
            ("Meta", {"fields": ["title"]}),  # repeated on purpose
        ]

    assert Grouped(_FieldModel, None).fieldset_fields(None) == ["title", "body"]


def test_a_field_no_section_names_is_not_editable():
    """Reading the editable set from `fields` while rendering from `fieldsets`
    would let a field be saved that was never on the page."""
    from buraq.contrib.admin.helpers import get_form_fields

    class Grouped(ModelAdmin):
        fields = ["title", "body", "secret"]
        fieldsets = [("Content", {"fields": ["title", "body"]})]

    by_name = {f["name"]: f for f in get_form_fields(Grouped(_FieldModel, None))}
    assert by_name["title"]["readonly"] is False
    assert by_name["secret"]["readonly"] is True, "left out of every section"


def test_a_value_posted_for_an_unlisted_field_is_dropped():
    """The other half of the same rule -- the form is not the only way a value
    arrives, since anyone can post one."""
    from buraq.contrib.admin.helpers import coerce_form_data

    class Grouped(ModelAdmin):
        fields = ["title", "secret"]
        fieldsets = [("Content", {"fields": ["title"]})]

    data = coerce_form_data({"title": "ok", "secret": "smuggled"}, Grouped(_FieldModel, None))
    assert "title" in data
    assert "secret" not in data
