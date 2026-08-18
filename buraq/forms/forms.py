"""
Forms — Form and ModelForm base classes with validation and rendering.

Usage:
    from buraq.forms import Form, ModelForm
    from buraq.forms.fields import CharField, IntegerField, EmailField

    class ContactForm(Form):
        name    = CharField(max_length=100)
        email   = EmailField()
        message = TextareaField()

    # In a view:
    async def contact(request):
        if request.method == "POST":
            form = ContactForm(data=dict(await request.form()))
            if await form.is_valid():
                name = form.cleaned_data["name"]
                ...
            return await render(request, "contact.html", {"form": form})
        return await render(request, "contact.html", {"form": ContactForm()})

    # ModelForm:
    class PostForm(ModelForm):
        class Meta:
            model = Post
            fields = ["title", "content"]

    form = PostForm(data=dict(await request.form()))
    if await form.is_valid():
        post = await form.save()
"""
from buraq.exceptions import NON_FIELD_ERRORS, ValidationError
from buraq.forms.fields import Field


class ErrorList(list):
    """A list of form field errors that can render itself as HTML."""

    def as_ul(self) -> str:
        if not self:
            return ""
        items = "".join(f"<li>{e}</li>" for e in self)
        return f'<ul class="errorlist">{items}</ul>'

    def as_text(self) -> str:
        return "\n".join(f"* {e}" for e in self)

    def __str__(self):
        return self.as_ul()

    def as_data(self) -> list:
        return list(self)


class ErrorDict(dict):
    """A dict of {field: ErrorList} that can render itself."""

    def as_ul(self) -> str:
        if not self:
            return ""
        parts = []
        for field, errors in self.items():
            error_list = ErrorList(errors) if not isinstance(errors, ErrorList) else errors
            parts.append(f"<li>{field}{error_list.as_ul()}</li>")
        return '<ul class="errorlist">' + "".join(parts) + "</ul>"

    def as_text(self) -> str:
        return "\n".join(
            f"{field}\n" + "\n".join(f"  * {e}" for e in errors)
            for field, errors in self.items()
        )

    def __str__(self):
        return self.as_ul()


BLANK_CHOICE_LABEL = "---------"

class MediaDefiningClass(type):
    """Metaclass that collects CSS/JS Media from fields and the class itself."""

    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        return cls


class Stylesheet:
    """
    A CSS stylesheet path with optional HTML attributes.

    Use inside a ``Media.css`` dict to add custom attributes (e.g. ``media``
    or ``crossorigin``) to the generated ``<link>`` tag::

        class MyForm(Form):
            class Media:
                css = {
                    "all": [
                        Stylesheet("/static/print.css", media="print"),
                        Stylesheet("/static/shared.css", crossorigin="anonymous"),
                    ]
                }

    Plain string paths continue to work alongside ``Stylesheet`` objects.
    """

    def __init__(self, path: str, **attrs):
        self.path = path
        self.attrs = attrs

    def __str__(self) -> str:
        return self.path

    def render(self, medium: str = "all") -> str:
        attrs_str = ""
        for k, v in self.attrs.items():
            attrs_str += f' {k}="{v}"'
        used_medium = self.attrs.get("media", medium)
        return (
            f'<link href="{self.path}" type="text/css"'
            f' media="{used_medium}" rel="stylesheet"{attrs_str}>'
        )


class Media:
    """
    Tracks CSS and JavaScript dependencies for forms and widgets.

    Usage::

        class MyForm(Form):
            class Media:
                css = {"all": ["myapp/css/widget.css"]}
                js  = ["myapp/js/widget.js"]
    """

    def __init__(self, media=None, css=None, js=None):
        if media:
            css = getattr(media, "css", {})
            js = getattr(media, "js", [])
        self._css = css or {}
        self._js = list(js or [])

    @property
    def css(self) -> dict:
        return self._css

    @property
    def js(self) -> list:
        return self._js

    def render_css(self) -> str:
        lines = []
        for medium, sheets in self._css.items():
            for sheet in sheets:
                if isinstance(sheet, Stylesheet):
                    lines.append(sheet.render(medium))
                else:
                    lines.append(
                        f'<link href="{sheet}" type="text/css" media="{medium}" rel="stylesheet">'
                    )
        return "\n".join(lines)

    def render_js(self) -> str:
        return "\n".join(f'<script src="{src}"></script>' for src in self._js)

    def render(self) -> str:
        return f"{self.render_css()}\n{self.render_js()}".strip()

    def __add__(self, other: "Media") -> "Media":
        css = dict(self._css)
        for medium, sheets in other._css.items():
            css.setdefault(medium, []).extend(sheets)
        js = list(dict.fromkeys(self._js + other._js))
        return Media(css=css, js=js)

    def __str__(self):
        return self.render()


class DeclarativeFieldsMetaclass(type):
    """Collect Field instances declared on the class body."""

    def __new__(mcs, name, bases, attrs):
        declared_fields = {}

        # Collect from base classes first
        for base in reversed(bases):
            if hasattr(base, "declared_fields"):
                declared_fields.update(base.declared_fields)

        # Collect from this class
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                declared_fields[key] = value
                attrs.pop(key)  # remove from class dict — live on declared_fields

        attrs["declared_fields"] = declared_fields
        return super().__new__(mcs, name, bases, attrs)


class BaseForm:
    def __init__(self, data=None, files=None, initial=None, prefix=None, auto_id="id_%s"):
        self.data = data or {}
        self.files = files or {}
        self.initial = initial or {}
        self.prefix = prefix
        self.auto_id = auto_id
        self._errors = None
        self._cleaned_data = None

    @property
    def fields(self):
        return dict(self.declared_fields)

    @property
    def cleaned_data(self) -> dict:
        return self._cleaned_data or {}

    @property
    def errors(self) -> dict:
        return self._errors or {}

    async def is_valid(self) -> bool:
        """
        Validate all fields and return True if no errors.

        Usage:
            form = PostForm(data=dict(await request.form()))
            if await form.is_valid():
                post = await form.save()
        """
        import inspect
        self._errors = {}
        self._cleaned_data = {}

        # Validate each field
        for name, field in self.fields.items():
            raw_value = self.data.get(name, field.initial)
            try:
                value = field.clean(raw_value)
                self._cleaned_data[name] = value
                cleaner = getattr(self, f"clean_{name}", None)
                if cleaner:
                    value = (
                        await cleaner(value) if inspect.iscoroutinefunction(cleaner)
                        else cleaner(value)
                    )
                    self._cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e.message)

        # Cross-field validation
        try:
            result = self.clean()
            if inspect.iscoroutine(result):
                result = await result
            if result is not None:
                self._cleaned_data = result
        except ValidationError as e:
            self.add_error(NON_FIELD_ERRORS, e.message)

        return not self._errors

    async def clean(self):
        """Override for cross-field validation. Can be sync or async."""
        return self._cleaned_data

    def add_error(self, field, error) -> None:
        if self._errors is None:
            self._errors = {}
        if field not in self._errors:
            self._errors[field] = []
        if isinstance(error, (list, tuple)):
            self._errors[field].extend([str(e) for e in error])
        else:
            self._errors[field].append(str(error))
        # Remove from cleaned_data if field had an error
        if field in (self._cleaned_data or {}):
            del self._cleaned_data[field]

    def non_field_errors(self) -> list:
        return self.errors.get(NON_FIELD_ERRORS, [])

    def has_error(self, field, code=None) -> bool:
        return field in self.errors

    def __iter__(self):
        """Iterate over BoundField instances."""
        for name in self.fields:
            yield BoundField(self, self.fields[name], name)

    def __getitem__(self, name) -> "BoundField":
        return BoundField(self, self.fields[name], name)

    def __repr__(self):
        return f"<{self.__class__.__name__} bound={bool(self.data)}>"

    # ── HTML rendering ──────────────────────────────────────────────────────

    def _html_errors(self, field_name: str) -> str:
        errs = self.errors.get(field_name, [])
        if not errs:
            return ""
        items = "".join(f"<li>{e}</li>" for e in errs)
        return f'<ul class="errorlist">{items}</ul>'

    def _render_field(self, bf: "BoundField") -> str:
        value = bf.value
        name = bf.html_name
        ftype = getattr(bf.field, "widget", None) or "text"
        if ftype == "textarea":
            widget = f'<textarea name="{name}" id="id_{name}">{value or ""}</textarea>'
        elif ftype == "password":
            widget = f'<input type="password" name="{name}" id="id_{name}">'
        elif ftype == "hidden":
            widget = f'<input type="hidden" name="{name}" value="{value or ""}">'
        elif hasattr(bf.field, "choices") and bf.field.choices:
            opts = "".join(
                f'<option value="{k}"'
                f'{"  selected" if str(k) == str(value) else ""}>{label}</option>'
                for k, label in bf.field.choices
            )
            widget = f'<select name="{name}" id="id_{name}">{opts}</select>'
        else:
            widget = f'<input type="text" name="{name}" value="{value or ""}" id="id_{name}">'
        return widget

    def as_p(self) -> str:
        """Render form as <p> tags."""
        from markupsafe import Markup
        rows = []
        nfe = self.non_field_errors()
        if nfe:
            rows.append('<ul class="errorlist nonfield">' +
                        "".join(f"<li>{e}</li>" for e in nfe) + "</ul>")
        for bf in self:
            errs = self._html_errors(bf.name)
            rows.append(
                f"{errs}<p>"
                f'<label for="id_{bf.html_name}">{bf.label}:</label> '
                f"{self._render_field(bf)}"
                f"</p>"
            )
        return Markup("\n".join(rows))

    def as_table(self) -> str:
        """Render form as <tr> rows (caller must wrap in <table>)."""
        from markupsafe import Markup
        rows = []
        nfe = self.non_field_errors()
        if nfe:
            rows.append(
                '<tr><td colspan="2"><ul class="errorlist nonfield">' +
                "".join(f"<li>{e}</li>" for e in nfe) + "</ul></td></tr>"
            )
        for bf in self:
            errs = self._html_errors(bf.name)
            rows.append(
                f"<tr>"
                f'<th><label for="id_{bf.html_name}">{bf.label}:</label></th>'
                f"<td>{errs}{self._render_field(bf)}</td>"
                f"</tr>"
            )
        return Markup("\n".join(rows))

    def as_div(self) -> str:
        """Render form as <div> blocks."""
        from markupsafe import Markup
        rows = []
        nfe = self.non_field_errors()
        if nfe:
            rows.append('<div class="errorlist nonfield">' +
                        "".join(f"<p>{e}</p>" for e in nfe) + "</div>")
        for bf in self:
            errs = self._html_errors(bf.name)
            rows.append(
                f'<div class="form-group">'
                f'<label for="id_{bf.html_name}">{bf.label}</label>'
                f"{errs}{self._render_field(bf)}"
                f"</div>"
            )
        return Markup("\n".join(rows))

    def as_ul(self) -> str:
        """Render form as <li> items (caller must wrap in <ul>)."""
        from markupsafe import Markup
        rows = []
        nfe = self.non_field_errors()
        if nfe:
            rows.append('<li><ul class="errorlist nonfield">' +
                        "".join(f"<li>{e}</li>" for e in nfe) + "</ul></li>")
        for bf in self:
            errs = self._html_errors(bf.name)
            rows.append(
                f"<li>"
                f"{errs}"
                f'<label for="id_{bf.html_name}">{bf.label}:</label> '
                f"{self._render_field(bf)}"
                f"</li>"
            )
        return Markup("\n".join(rows))

    @property
    def changed_data(self) -> list:
        """List of field names that have changed from their initial values."""
        changed = []
        for name, field in self.fields.items():
            initial = self.initial.get(name, field.initial)
            data = self.data.get(name)
            if field.has_changed(initial, data):
                changed.append(name)
        return changed

    def hidden_fields(self) -> list:
        """Return BoundFields for hidden widget fields."""
        return [bf for bf in self if getattr(bf.field, "widget", None) == "hidden"]

    def visible_fields(self) -> list:
        """Return BoundFields for visible (non-hidden) fields."""
        return [bf for bf in self if getattr(bf.field, "widget", None) != "hidden"]

    @property
    def media(self) -> "Media":
        """Collect Media from all fields."""
        combined = Media()
        for field in self.fields.values():
            field_media = getattr(field, "media", None)
            if field_media:
                combined = combined + field_media
        meta_media = getattr(self.__class__, "Media", None)
        if meta_media:
            combined = combined + Media(meta_media)
        return combined


class Form(BaseForm, metaclass=DeclarativeFieldsMetaclass):
    """
    Base class for all forms.

    Usage:
        class LoginForm(Form):
            username = CharField(max_length=150)
            password = PasswordField()
    """


class ModelFormMetaclass(DeclarativeFieldsMetaclass):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)

        # Auto-generate fields from Meta.model if specified
        meta = attrs.get("Meta") or getattr(cls, "Meta", None)
        if meta and hasattr(meta, "model"):
            model = meta.model
            include_fields = getattr(meta, "fields", None)
            exclude_fields = getattr(meta, "exclude", [])

            if include_fields == "__all__":
                include_fields = None

            # Map SQLAlchemy column types → form fields
            import sqlalchemy as sa

            from buraq.forms.fields import (
                BooleanField,
                CharField,
                DateField,
                DateTimeField,
                DecimalField,
                FloatField,
                IntegerField,
                TextField,
            )

            type_map = {
                sa.String: CharField,
                sa.Text: lambda col: TextField(required=not col.nullable),
                sa.Integer: IntegerField,
                sa.BigInteger: IntegerField,
                sa.SmallInteger: IntegerField,
                sa.Float: FloatField,
                sa.Numeric: DecimalField,
                sa.Boolean: BooleanField,
                sa.Date: DateField,
                sa.DateTime: DateTimeField,
                sa.JSON: CharField,
            }

            if hasattr(model, "__table__"):
                for col in model.__table__.columns:
                    if col.name in ("id",):
                        continue
                    if include_fields and col.name not in include_fields:
                        continue
                    if col.name in exclude_fields:
                        continue
                    if col.name in cls.declared_fields:
                        continue  # explicit field declaration takes priority
                    for sa_type, form_field in type_map.items():
                        if isinstance(col.type, sa_type):
                            if callable(form_field) and not isinstance(form_field, type):
                                field = form_field(col)
                            else:
                                field = form_field(required=not col.nullable)
                            # Set max_length for String columns
                            if isinstance(col.type, sa.String) and col.type.length:
                                field.max_length = col.type.length
                            cls.declared_fields[col.name] = field
                            break

        return cls


class ModelForm(BaseForm, metaclass=ModelFormMetaclass):
    """
    Form tied to a Model — auto-generates fields from model columns.

    Usage:
        class PostForm(ModelForm):
            class Meta:
                model = Post
                fields = ["title", "content"]
                # or: fields = "__all__"
                # or: exclude = ["created_at"]

        form = PostForm(data={"title": "Hello", "content": "World"})
        if form.is_valid():
            post = await form.save()
    """

    def __init__(self, data=None, instance=None, **kwargs):
        self._instance = instance
        if instance and not data:
            instance_initial = {
                name: getattr(instance, name, None)
                for name in self.fields
            }
            # Instance values are the base; explicitly passed initial overrides them
            passed_initial = kwargs.get("initial") or {}
            kwargs["initial"] = {**instance_initial, **passed_initial}
        super().__init__(data=data, **kwargs)

    async def save(self, commit: bool = True):
        """
        Create or update the model instance from cleaned_data.

        When commit=False, the instance is built but NOT written to the database.
        Call await instance.save() manually when ready.
        """
        if not self._cleaned_data:
            await self.is_valid()
        if self._errors:
            raise ValidationError("Cannot save an invalid form.")

        meta = getattr(self.__class__, "Meta", None)
        if not meta or not hasattr(meta, "model"):
            raise ValueError("ModelForm must define class Meta with model = ...")

        model = meta.model
        data = dict(self.cleaned_data)

        if self._instance:
            for key, value in data.items():
                setattr(self._instance, key, value)
            if commit:
                await self._instance.save()
            return self._instance
        else:
            if commit:
                obj = await model.objects.create(**data)
                self._instance = obj
                return obj
            else:
                # Build unsaved instance — caller is responsible for saving
                obj = model(**data)
                self._instance = obj
                return obj


class BoundField:
    """A field bound to a form — wraps field with form context."""

    def __init__(self, form: BaseForm, field: Field, name: str):
        self.form = form
        self.field = field
        self.name = name
        self.html_name = f"{form.prefix}-{name}" if form.prefix else name
        self.label = field.label or name.replace("_", " ").title()
        self.help_text = field.help_text

    @property
    def id_for_label(self) -> str:
        """The HTML id attribute value for this field's widget."""
        return f"id_{self.html_name}"

    @property
    def value(self):
        data = self.form.data.get(self.name)
        if data is None:
            val = self.form.initial.get(self.name, self.field.initial)
            return "" if val is None else val
        return data

    @property
    def errors(self) -> ErrorList:
        errs = self.form.errors.get(self.name, [])
        return errs if isinstance(errs, ErrorList) else ErrorList(errs)

    def label_tag(self, contents: str = None, attrs: dict = None, label_suffix: str = ":") -> str:
        """Render a <label> tag for this field."""
        from markupsafe import Markup
        label = contents or self.label
        extra = ""
        if attrs:
            extra = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())
        return Markup(f'<label for="{self.id_for_label}"{extra}>{label}{label_suffix}</label>')

    def css_classes(self, extra_classes: str = "") -> str:
        """Return a space-joined string of CSS classes for this field's wrapper element."""
        classes = []
        if self.errors:
            classes.append("error")
        if self.field.required:
            classes.append("required")
        if extra_classes:
            classes.extend(extra_classes.split())
        return " ".join(classes)

    def build_widget_attrs(self, attrs: dict = None, widget=None) -> dict:
        """Return attrs dict with id and name added."""
        result = {"name": self.html_name, "id": self.id_for_label}
        if attrs:
            result.update(attrs)
        return result

    def as_widget(self, widget=None, attrs: dict = None) -> str:
        """Render this field's widget as HTML."""
        from markupsafe import Markup
        return Markup(self.form._render_field(self))

    def as_text(self, attrs: dict = None) -> str:
        """Render as a text <input>."""
        from markupsafe import Markup
        v = self.value
        a = self.build_widget_attrs(attrs)
        attr_str = " ".join(f'{k}="{v2}"' for k, v2 in a.items())
        return Markup(f'<input type="text" value="{v or ""}" {attr_str}>')

    def as_textarea(self, attrs: dict = None) -> str:
        """Render as a <textarea>."""
        from markupsafe import Markup
        v = self.value
        a = self.build_widget_attrs(attrs)
        attr_str = " ".join(f'{k}="{v2}"' for k, v2 in a.items())
        return Markup(f"<textarea {attr_str}>{v or ''}</textarea>")

    def as_hidden(self, attrs: dict = None) -> str:
        """Render as a hidden <input>."""
        from markupsafe import Markup
        v = self.value
        a = self.build_widget_attrs(attrs)
        attr_str = " ".join(f'{k}="{v2}"' for k, v2 in a.items())
        return Markup(f'<input type="hidden" value="{v or ""}" {attr_str}>')

    def __str__(self):
        return str(self.value or "")

    def __repr__(self):
        return f"<BoundField {self.name}={self.value!r}>"


# ── Formsets (canonical implementations live in forms/formsets.py) ────────────


class SuccessMessageMixin:
    """
    Mixin for CBVs that adds a success message on successful form submission.

    Usage::

        class PostCreateView(SuccessMessageMixin, CreateView):
            model         = Post
            success_url   = "/posts"
            success_message = "Post %(title)s was created."
    """

    success_message: str = ""

    def get_success_message(self, cleaned_data: dict) -> str:
        return self.success_message % cleaned_data

    async def form_valid(self, form):
        response = await super().form_valid(form)
        msg = self.get_success_message(form.cleaned_data)
        if msg:
            try:
                from buraq.contrib.messages import success as _success
                _success(self.request, msg)
            except Exception:
                pass
        return response
