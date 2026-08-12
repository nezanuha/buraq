"""
Formsets — manage a collection of forms for editing multiple instances at once.

Usage::

    from buraq.forms import Form
    from buraq.forms.fields import CharField, IntegerField
    from buraq.forms.formsets import formset_factory

    class BookForm(Form):
        title  = CharField(max_length=200)
        pages  = IntegerField(min_value=1)

    BookFormSet = formset_factory(BookForm, extra=2)

    # In a view:
    async def manage_books(request):
        if request.method == "POST":
            formset = BookFormSet(data=dict(await request.form()))
            if await formset.is_valid():
                for form in formset.forms:
                    save_book(form.cleaned_data)
                return redirect("/books")
        else:
            formset = BookFormSet()
        return render(request, "books.html", {"formset": formset})
"""
from __future__ import annotations

from buraq.exceptions import ValidationError
from buraq.forms.forms import BaseForm, Form

TOTAL_FORM_COUNT = "TOTAL_FORMS"
INITIAL_FORM_COUNT = "INITIAL_FORMS"
MIN_NUM_FORM_COUNT = "MIN_NUM_FORMS"
MAX_NUM_FORM_COUNT = "MAX_NUM_FORMS"
ORDERING_FIELD_NAME = "ORDER"
DELETION_FIELD_NAME = "DELETE"

DEFAULT_MIN_NUM = 0
DEFAULT_MAX_NUM = 1000


class ManagementForm(Form):
    """Hidden form that tracks form counts in the formset."""

    from buraq.forms.fields import IntegerField

    TOTAL_FORMS = IntegerField()
    INITIAL_FORMS = IntegerField()
    MIN_NUM_FORMS = IntegerField(required=False)
    MAX_NUM_FORMS = IntegerField(required=False)


class BaseFormSet:
    """
    A collection of forms that can be submitted together.

    Do not use directly; use ``formset_factory`` to create a subclass.
    """

    form_class: type[BaseForm] = None
    extra: int = 1
    can_order: bool = False
    can_delete: bool = False
    min_num: int = DEFAULT_MIN_NUM
    max_num: int = DEFAULT_MAX_NUM
    absolute_max: int = DEFAULT_MAX_NUM + DEFAULT_MAX_NUM
    validate_min: bool = False
    validate_max: bool = False

    def __init__(
        self,
        data: dict | None = None,
        files: dict | None = None,
        initial: list | None = None,
        prefix: str = "form",
    ):
        self.data = data or {}
        self.files = files or {}
        self.initial = initial or []
        self.prefix = prefix
        self._errors: list | None = None
        self._non_form_errors: list = []
        self._forms: list | None = None

    # ── Management form ──────────────────────────────────────────────────────

    def _management_form_prefix(self) -> str:
        return f"{self.prefix}-"

    def _get_management_data(self) -> dict:
        p = self._management_form_prefix()
        return {
            TOTAL_FORM_COUNT: self.data.get(f"{p}{TOTAL_FORM_COUNT}", self.total_form_count()),
            INITIAL_FORM_COUNT: self.data.get(f"{p}{INITIAL_FORM_COUNT}", len(self.initial)),
            MIN_NUM_FORM_COUNT: self.min_num,
            MAX_NUM_FORM_COUNT: self.max_num,
        }

    def total_form_count(self) -> int:
        p = self._management_form_prefix()
        raw = self.data.get(f"{p}{TOTAL_FORM_COUNT}")
        if raw is not None:
            try:
                return min(int(raw), self.absolute_max)
            except (ValueError, TypeError):
                pass
        return len(self.initial) + self.extra

    def initial_form_count(self) -> int:
        p = self._management_form_prefix()
        raw = self.data.get(f"{p}{INITIAL_FORM_COUNT}")
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
        return len(self.initial)

    # ── Forms ────────────────────────────────────────────────────────────────

    def _construct_form(self, index: int) -> BaseForm:
        form_prefix = f"{self.prefix}-{index}"
        form_data: dict | None = None
        form_initial: dict | None = None

        if self.data:
            form_data = {
                k[len(form_prefix) + 1:]: v
                for k, v in self.data.items()
                if k.startswith(f"{form_prefix}-")
            }

        if index < len(self.initial):
            form_initial = self.initial[index]

        form = self.form_class(
            data=form_data,
            initial=form_initial or {},
            prefix=form_prefix,
        )

        # Inject ORDER and DELETE pseudo-fields so templates can render them
        if self.can_order:
            from buraq.forms.fields import IntegerField
            order_field = IntegerField(required=False, label="Order")
            form.declared_fields = dict(form.declared_fields)
            form.declared_fields[ORDERING_FIELD_NAME] = order_field
            if form_data is not None:
                order_value = form_data.get(ORDERING_FIELD_NAME)
                form._order_value = int(order_value) if order_value is not None else index
            else:
                form._order_value = index

        if self.can_delete:
            from buraq.forms.fields import BooleanField
            delete_field = BooleanField(required=False, label="Delete")
            form.declared_fields = dict(form.declared_fields)
            form.declared_fields[DELETION_FIELD_NAME] = delete_field

        return form

    @property
    def forms(self) -> list[BaseForm]:
        if self._forms is None:
            self._forms = [
                self._construct_form(i) for i in range(self.total_form_count())
            ]
        return self._forms

    @property
    def initial_forms(self) -> list[BaseForm]:
        return self.forms[: self.initial_form_count()]

    @property
    def extra_forms(self) -> list[BaseForm]:
        return self.forms[self.initial_form_count():]

    def _is_form_empty(self, form: BaseForm) -> bool:
        for field_name, _field in form.fields.items():
            value = form.data.get(field_name)
            if value not in (None, "", [], {}):
                return False
        return True

    # ── Validation ───────────────────────────────────────────────────────────

    async def is_valid(self) -> bool:
        self._errors = []
        self._non_form_errors = []
        all_valid = True

        for i, form in enumerate(self.forms):
            if self._is_form_empty(form) and i >= self.initial_form_count():
                # Always append so len(self._errors) == len(self.forms)
                self._errors.append({})
                continue
            if not await form.is_valid():
                all_valid = False
                self._errors.append(form.errors)
            else:
                self._errors.append({})

        try:
            await self.clean()
        except ValidationError as e:
            self._non_form_errors = [str(e)]
            all_valid = False

        if self.validate_min and self._filled_count() < self.min_num:
            self._non_form_errors.append(
                f"Please submit at least {self.min_num} form(s)."
            )
            all_valid = False

        if self.validate_max and self._filled_count() > self.max_num:
            self._non_form_errors.append(
                f"Please submit at most {self.max_num} form(s)."
            )
            all_valid = False

        return all_valid

    def _filled_count(self) -> int:
        return sum(
            1 for i, f in enumerate(self.forms)
            if not (self._is_form_empty(f) and i >= self.initial_form_count())
        )

    async def clean(self):
        """Override for cross-formset validation. Raise ValidationError to abort."""

    def non_form_errors(self) -> list[str]:
        return self._non_form_errors

    @property
    def errors(self) -> list[dict]:
        return self._errors or [{} for _ in self.forms]

    # ── Cleaned data helpers ─────────────────────────────────────────────────

    @property
    def cleaned_data(self) -> list[dict]:
        result = []
        for f in self.forms:
            if not f.cleaned_data or self._is_form_empty(f):
                continue
            data = dict(f.cleaned_data)
            if self.can_delete and data.get(DELETION_FIELD_NAME):
                continue  # omit deleted forms from cleaned_data
            result.append(data)
        return result

    @property
    def deleted_forms(self) -> list:
        """Forms marked for deletion (only when can_delete=True)."""
        if not self.can_delete:
            return []
        deleted = []
        for f in self.forms:
            if f.cleaned_data and f.cleaned_data.get(DELETION_FIELD_NAME):
                deleted.append(f)
        return deleted

    @property
    def ordered_forms(self) -> list:
        """Forms sorted by their ORDER field value (only when can_order=True)."""
        if not self.can_order:
            return list(self.forms)
        return sorted(self.forms, key=lambda f: getattr(f, "_order_value", 0))

    # ── HTML helpers ─────────────────────────────────────────────────────────

    def management_form_html(self) -> str:
        p = self._management_form_prefix()
        d = self._get_management_data()
        return (
            f'<input type="hidden" name="{p}{TOTAL_FORM_COUNT}" value="{d[TOTAL_FORM_COUNT]}">'
            f'<input type="hidden" name="{p}{INITIAL_FORM_COUNT}" value="{d[INITIAL_FORM_COUNT]}">'
            f'<input type="hidden" name="{p}{MIN_NUM_FORM_COUNT}" value="{d[MIN_NUM_FORM_COUNT]}">'
            f'<input type="hidden" name="{p}{MAX_NUM_FORM_COUNT}" value="{d[MAX_NUM_FORM_COUNT]}">'
        )

    def __iter__(self):
        return iter(self.forms)

    def __len__(self):
        return len(self.forms)


class BaseModelFormSet(BaseFormSet):
    """
    A ``BaseFormSet`` that also knows how to save model instances.
    """

    model = None

    async def save(self, commit: bool = True) -> list:
        """Save all non-empty valid forms. Returns the list of saved instances."""
        saved = []
        for i, form in enumerate(self.forms):
            if not form.cleaned_data:
                continue
            if self._is_form_empty(form) and i >= self.initial_form_count():
                continue
            if hasattr(form, "save"):
                obj = await form.save(commit=commit)
                saved.append(obj)
        return saved


class BaseInlineFormSet(BaseModelFormSet):
    """
    A ``BaseModelFormSet`` for editing child objects related to a parent.
    """

    fk_field: str = ""
    parent_instance = None

    async def save(self, commit: bool = True) -> list:
        saved = []
        for i, form in enumerate(self.forms):
            if not form.cleaned_data:
                continue
            if self._is_form_empty(form) and i >= self.initial_form_count():
                continue
            if hasattr(form, "save"):
                obj = await form.save(commit=False)
                if self.fk_field and self.parent_instance is not None:
                    setattr(obj, self.fk_field, self.parent_instance.id)
                if commit:
                    await obj.save()
                saved.append(obj)
        return saved


# ── Factory functions ────────────────────────────────────────────────────────

def formset_factory(
    form: type[BaseForm],
    formset: type[BaseFormSet] = BaseFormSet,
    extra: int = 1,
    can_order: bool = False,
    can_delete: bool = False,
    min_num: int = DEFAULT_MIN_NUM,
    max_num: int = DEFAULT_MAX_NUM,
    validate_min: bool = False,
    validate_max: bool = False,
) -> type[BaseFormSet]:
    """
    Return a ``FormSet`` class for the given ``form`` class.

    Args:
        form:          The ``Form`` class to wrap.
        formset:       Base formset class (default: ``BaseFormSet``).
        extra:         Number of extra blank forms to display.
        can_order:     Allow user to reorder forms.
        can_delete:    Show a DELETE checkbox on each form.
        min_num:       Minimum number of filled forms required.
        max_num:       Maximum number of filled forms allowed.
        validate_min:  Enforce ``min_num`` during validation.
        validate_max:  Enforce ``max_num`` during validation.

    Usage::

        ArticleFormSet = formset_factory(ArticleForm, extra=3)
    """
    attrs = {
        "form_class": form,
        "extra": extra,
        "can_order": can_order,
        "can_delete": can_delete,
        "min_num": min_num,
        "max_num": max_num,
        "validate_min": validate_min,
        "validate_max": validate_max,
        "absolute_max": max_num + DEFAULT_MAX_NUM,
    }
    return type(f"{form.__name__}FormSet", (formset,), attrs)


def modelformset_factory(
    model,
    form=None,
    formset: type[BaseModelFormSet] = BaseModelFormSet,
    extra: int = 1,
    can_delete: bool = False,
    min_num: int = DEFAULT_MIN_NUM,
    max_num: int = DEFAULT_MAX_NUM,
    validate_min: bool = False,
    validate_max: bool = False,
    fields=None,
    exclude=None,
) -> type[BaseModelFormSet]:
    """
    Return a ``ModelFormSet`` class for the given ``model``.

    A ``ModelForm`` is auto-generated if ``form`` is not provided.

    Usage::

        ArticleFormSet = modelformset_factory(Article, fields=["title", "body"], extra=2)
        formset = ArticleFormSet(data=dict(await request.form()))
        if await formset.is_valid():
            await formset.save()
    """
    from buraq.forms.forms import ModelForm

    if form is None:
        meta_attrs: dict = {"model": model}
        if fields is not None:
            meta_attrs["fields"] = fields
        if exclude is not None:
            meta_attrs["exclude"] = exclude
        Meta = type("Meta", (), meta_attrs)
        form = type(f"{model.__name__}Form", (ModelForm,), {"Meta": Meta})

    attrs = {
        "form_class": form,
        "model": model,
        "extra": extra,
        "can_delete": can_delete,
        "min_num": min_num,
        "max_num": max_num,
        "validate_min": validate_min,
        "validate_max": validate_max,
        "absolute_max": max_num + DEFAULT_MAX_NUM,
    }
    return type(f"{model.__name__}FormSet", (formset,), attrs)


def inlineformset_factory(
    parent_model,
    model,
    fk_field: str = "",
    form=None,
    formset: type[BaseInlineFormSet] = BaseInlineFormSet,
    extra: int = 3,
    can_delete: bool = True,
    min_num: int = DEFAULT_MIN_NUM,
    max_num: int = DEFAULT_MAX_NUM,
    validate_min: bool = False,
    validate_max: bool = False,
    fields=None,
    exclude=None,
) -> type[BaseInlineFormSet]:
    """
    Return an ``InlineFormSet`` class for editing ``model`` instances related
    to a ``parent_model`` instance via a ForeignKey.

    Args:
        parent_model: The parent model class.
        model:        The child model class (has a FK to ``parent_model``).
        fk_field:     Name of the FK field on ``model``. Auto-detected if omitted.

    Usage::

        CommentFormSet = inlineformset_factory(Post, Comment, fk_field="post_id", extra=2)

        # In a view:
        post = await Post.objects.get(id=pk)
        formset = CommentFormSet(
            data=dict(await request.form()),
            initial=[...],  # existing comments
        )
        formset.parent_instance = post
        if await formset.is_valid():
            await formset.save()
    """
    from buraq.forms.forms import ModelForm

    if not fk_field:
        # Auto-detect: find a column whose name ends with "_id" and whose FK
        # references the parent table.
        parent_table = getattr(parent_model, "__tablename__", None)
        for col in model.__table__.columns:
            for fk in col.foreign_keys:
                if parent_table and fk.column.table.name == parent_table:
                    fk_field = col.name
                    break
            if fk_field:
                break

    if form is None:
        meta_attrs: dict = {"model": model}
        if fields is not None:
            meta_attrs["fields"] = fields
        if exclude is not None:
            meta_attrs["exclude"] = exclude
        Meta = type("Meta", (), meta_attrs)
        form = type(f"{model.__name__}Form", (ModelForm,), {"Meta": Meta})

    attrs = {
        "form_class": form,
        "model": model,
        "fk_field": fk_field,
        "extra": extra,
        "can_delete": can_delete,
        "min_num": min_num,
        "max_num": max_num,
        "validate_min": validate_min,
        "validate_max": validate_max,
        "absolute_max": max_num + DEFAULT_MAX_NUM,
    }
    return type(f"{model.__name__}InlineFormSet", (formset,), attrs)
