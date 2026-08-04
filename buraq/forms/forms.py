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
            return render(request, "contact.html", {"form": form})
        return render(request, "contact.html", {"form": ContactForm()})

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
        """Create or update the model instance from cleaned_data."""
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
            obj = await model.objects.create(**data)
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
    def value(self):
        data = self.form.data.get(self.name)
        if data is None:
            val = self.form.initial.get(self.name, self.field.initial)
            return "" if val is None else val
        return data

    @property
    def errors(self) -> list:
        return self.form.errors.get(self.name, [])

    def __str__(self):
        return str(self.value or "")

    def __repr__(self):
        return f"<BoundField {self.name}={self.value!r}>"
