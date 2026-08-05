"""
Form fields — built-in field types with validation.
"""
import re
from datetime import date as _date
from datetime import datetime as _datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from buraq.exceptions import ValidationError


class Field:
    """Base form field."""

    default_error_messages = {
        "required": "This field is required.",
        "invalid": "Enter a valid value.",
    }

    def __init__(
        self,
        required: bool = True,
        label: str = None,
        initial: Any = None,
        help_text: str = "",
        error_messages: dict = None,
        validators: list = None,
        disabled: bool = False,
        widget=None,
    ):
        self.required = required
        self.label = label
        self.initial = initial
        self.help_text = help_text
        self.disabled = disabled
        self.validators = validators or []
        self.widget = widget or {}  # widget hints (not rendered server-side by default)
        messages = dict(self.default_error_messages)
        if error_messages:
            messages.update(error_messages)
        self.error_messages = messages

    def to_python(self, value: Any) -> Any:
        """Coerce raw value to the right Python type."""
        return value

    def validate(self, value: Any) -> None:
        """Raise ValidationError for invalid values (after to_python)."""
        if self.required and value in (None, "", [], {}):
            raise ValidationError(self.error_messages["required"], code="required")

    def run_validators(self, value: Any) -> None:
        if value in (None, ""):
            return
        errors = []
        last_exc = None
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                errors.append(e.message)
                last_exc = e
        if errors:
            raise ValidationError(errors[0]) from last_exc

    def clean(self, value: Any) -> Any:
        """Full clean: to_python → validate → run_validators → return value."""
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value

    def has_changed(self, initial, data) -> bool:
        return initial != data


class CharField(Field):
    def __init__(
        self, max_length: int = None, min_length: int = None,
        strip: bool = True, empty_value: str = "", **kwargs
    ):
        super().__init__(**kwargs)
        self.max_length = max_length
        self.min_length = min_length
        self.strip = strip
        self.empty_value = empty_value

    def to_python(self, value):
        if value not in (None, ""):
            value = str(value)
            if self.strip:
                value = value.strip()
        if value == "":
            return self.empty_value
        return value

    def validate(self, value):
        super().validate(value)
        if value and self.max_length and len(value) > self.max_length:
            raise ValidationError(
                f"Ensure this value has at most {self.max_length} characters.",
                code="max_length",
            )
        if value and self.min_length and len(value) < self.min_length:
            raise ValidationError(
                f"Ensure this value has at least {self.min_length} characters.",
                code="min_length",
            )


class IntegerField(Field):
    def __init__(self, min_value: int = None, max_value: int = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            raise ValidationError("Enter a whole number.", code="invalid") from None

    def validate(self, value):
        super().validate(value)
        if value is None:
            return
        if self.min_value is not None and value < self.min_value:
            raise ValidationError(
                f"Ensure this value is greater than or equal to {self.min_value}.",
                code="min_value",
            )
        if self.max_value is not None and value > self.max_value:
            raise ValidationError(
                f"Ensure this value is less than or equal to {self.max_value}.",
                code="max_value",
            )


class FloatField(IntegerField):
    def to_python(self, value):
        if value in (None, ""):
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            raise ValidationError("Enter a number.", code="invalid") from None


class DecimalField(Field):
    def __init__(
        self, max_digits: int = None, decimal_places: int = None,
        min_value=None, max_value=None, **kwargs
    ):
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value).strip())
        except InvalidOperation:
            raise ValidationError("Enter a valid decimal number.", code="invalid") from None

    def validate(self, value):
        super().validate(value)
        if value is None:
            return
        if self.min_value is not None and value < self.min_value:
            raise ValidationError(
                f"Ensure this value is greater than or equal to {self.min_value}.",
                code="min_value",
            )
        if self.max_value is not None and value > self.max_value:
            raise ValidationError(
                f"Ensure this value is less than or equal to {self.max_value}.",
                code="max_value",
            )


class BooleanField(Field):
    def to_python(self, value):
        if isinstance(value, str) and value.lower() in ("false", "0", "off", "no", ""):
            return False
        return bool(value)

    def validate(self, value):
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")


class NullBooleanField(BooleanField):
    def to_python(self, value):
        if value in (True, "True", "true", "1", "on", "yes"):
            return True
        if value in (False, "False", "false", "0", "off", "no"):
            return False
        return None


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            from buraq.validators import validate_email
            validate_email(value)


class URLField(CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            from buraq.validators import validate_url
            validate_url(value)


class SlugField(CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            from buraq.validators import validate_slug
            validate_slug(value)


class DateField(Field):
    _default_input_formats = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y"]

    def __init__(self, input_formats=None, **kwargs):
        super().__init__(**kwargs)
        self.input_formats = input_formats or self._default_input_formats

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, _datetime):
            return value.date()
        if isinstance(value, _date):
            return value
        for fmt in self.input_formats:
            try:
                return _datetime.strptime(str(value).strip(), fmt).date()
            except (ValueError, TypeError):
                continue
        raise ValidationError("Enter a valid date.", code="invalid")


class DateTimeField(Field):
    input_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, _datetime):
            return value
        for fmt in self.input_formats:
            try:
                return _datetime.strptime(str(value).strip(), fmt)
            except (ValueError, TypeError):
                continue
        raise ValidationError("Enter a valid date/time.", code="invalid")


class TimeField(Field):
    def to_python(self, value):
        if value in (None, ""):
            return None
        from datetime import time as time_type
        if isinstance(value, time_type):
            return value
        for fmt in ["%H:%M:%S", "%H:%M"]:
            try:
                return _datetime.strptime(str(value).strip(), fmt).time()
            except (ValueError, TypeError):
                continue
        raise ValidationError("Enter a valid time.", code="invalid")


class ChoiceField(Field):
    def __init__(self, choices: list, **kwargs):
        super().__init__(**kwargs)
        self.choices = choices  # [(value, label), ...]

    def to_python(self, value):
        if value == "" or value is None:
            return ""
        return str(value)

    def validate(self, value):
        super().validate(value)
        if value and value not in [str(k) for k, _ in self.choices]:
            raise ValidationError(
                f"Select a valid choice. {value} is not one of the available choices.",
                code="invalid_choice",
                params={"value": value},
            )


class MultipleChoiceField(ChoiceField):
    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    def validate(self, value):
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")
        valid = [str(k) for k, _ in self.choices]
        for v in value:
            if str(v) not in valid:
                raise ValidationError(
                    f"Select a valid choice. {v} is not one of the available choices.",
                    code="invalid_choice",
                )


class TypedChoiceField(ChoiceField):
    def __init__(self, coerce=str, empty_value="", **kwargs):
        self.coerce = coerce
        self.empty_value = empty_value
        super().__init__(**kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value == self.empty_value or value in (None, ""):
            return self.empty_value
        try:
            return self.coerce(value)
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages["invalid"], code="invalid") from None


class FileField(Field):
    def to_python(self, value):
        if not value:
            return None
        return value  # starlette UploadFile or similar


class ImageField(FileField):
    def validate(self, value):
        super().validate(value)
        # Basic image type check
        if value and hasattr(value, "content_type") and not value.content_type.startswith("image/"):
            raise ValidationError("Upload a valid image.", code="invalid_image")


class UUIDField(Field):
    def to_python(self, value):
        if value in (None, ""):
            return None
        import uuid
        try:
            return uuid.UUID(str(value).strip())
        except (AttributeError, ValueError):
            raise ValidationError("Enter a valid UUID.", code="invalid") from None


class JSONField(Field):
    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        import json
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValidationError("Enter a valid JSON.", code="invalid") from exc


class RegexField(CharField):
    def __init__(self, regex: str, **kwargs):
        super().__init__(**kwargs)
        self.regex = re.compile(regex)

    def validate(self, value):
        super().validate(value)
        if value and not self.regex.search(value):
            raise ValidationError("Enter a valid value.", code="invalid")


class TextField(CharField):
    """Multi-line text field — renders as <textarea>."""
    widget = "textarea"


class PasswordField(CharField):
    """CharField that masks input."""
    widget = "password"


class HiddenField(CharField):
    """CharField rendered as hidden input."""
    widget = "hidden"


class IPAddressField(CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            import ipaddress
            try:
                ipaddress.ip_address(value)
            except ValueError:
                raise ValidationError("Enter a valid IP address.", code="invalid") from None


class GenericIPAddressField(IPAddressField):
    pass


class ModelChoiceField(Field):
    """
    Select a single model instance from a queryset.

    Usage:
        author = ModelChoiceField(queryset=User.objects.filter(is_active=True))
        selected_user = await form.fields["author"].fetch(pk_value)
    """

    def __init__(self, queryset, empty_label: str = "---------", **kwargs):
        super().__init__(**kwargs)
        self.queryset = queryset
        self.empty_label = empty_label

    def to_python(self, value):
        if value in (None, "", "None"):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValidationError("Select a valid choice.", code="invalid_choice") from None

    def validate(self, value):
        if self.required and value is None:
            raise ValidationError(self.error_messages["required"], code="required")

    async def fetch(self, pk):
        """Return the model instance matching pk, or raise ValidationError."""
        if pk is None:
            return None
        try:
            return await self.queryset.filter(id=pk).first()
        except Exception:
            raise ValidationError("Select a valid choice.", code="invalid_choice") from None


class ModelMultipleChoiceField(ModelChoiceField):
    """
    Select multiple model instances from a queryset.

    Usage:
        tags = ModelMultipleChoiceField(queryset=Tag.objects.all())
        selected_tags = await form.fields["tags"].fetch_many(pk_values)
    """

    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        try:
            return [int(v) for v in value]
        except (ValueError, TypeError):
            raise ValidationError("Select valid choices.", code="invalid_choice") from None

    def validate(self, value):
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")

    async def fetch_many(self, pks: list):
        """Return a list of model instances matching the given pks."""
        if not pks:
            return []
        return await self.queryset.filter(id__in=pks).all()


class TypedMultipleChoiceField(MultipleChoiceField):
    """MultipleChoiceField that coerces values to a given type."""

    def __init__(self, coerce=str, **kwargs):
        self.coerce = coerce
        super().__init__(**kwargs)

    def to_python(self, value):
        values = super().to_python(value)
        try:
            return [self.coerce(v) for v in values]
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages["invalid"], code="invalid") from None
