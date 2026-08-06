"""
Validators — callable objects that raise ValidationError on invalid input.

Usage:
    from buraq.validators import MinLengthValidator, RegexValidator

    class MyForm(Form):
        username = CharField(validators=[MinLengthValidator(3)])
"""
import re as _re

from buraq.exceptions import ValidationError


class MaxLengthValidator:
    def __init__(self, limit: int):
        self.limit = limit

    def __call__(self, value):
        if value and len(str(value)) > self.limit:
            n = len(str(value))
            raise ValidationError(
                f"Ensure this value has at most {self.limit} characters (it has {n}).",
                code="max_length",
                params={"limit_value": self.limit, "show_value": len(str(value))},
            )


class MinLengthValidator:
    def __init__(self, limit: int):
        self.limit = limit

    def __call__(self, value):
        if value and len(str(value)) < self.limit:
            n = len(str(value))
            raise ValidationError(
                f"Ensure this value has at least {self.limit} characters (it has {n}).",
                code="min_length",
                params={"limit_value": self.limit, "show_value": len(str(value))},
            )


class MaxValueValidator:
    def __init__(self, limit):
        self.limit = limit

    def __call__(self, value):
        if value is not None and value > self.limit:
            raise ValidationError(
                f"Ensure this value is less than or equal to {self.limit}.",
                code="max_value",
                params={"limit_value": self.limit, "show_value": value},
            )


class MinValueValidator:
    def __init__(self, limit):
        self.limit = limit

    def __call__(self, value):
        if value is not None and value < self.limit:
            raise ValidationError(
                f"Ensure this value is greater than or equal to {self.limit}.",
                code="min_value",
                params={"limit_value": self.limit, "show_value": value},
            )


class RegexValidator:
    def __init__(
        self, regex: str, message: str = "Enter a valid value.",
        code: str = "invalid", inverse_match: bool = False
    ):
        self.regex = _re.compile(regex)
        self.message = message
        self.code = code
        self.inverse_match = inverse_match

    def __call__(self, value):
        match = self.regex.search(str(value))
        if (not match) != self.inverse_match:
            raise ValidationError(self.message, code=self.code)


class EmailValidator:
    message = "Enter a valid email address."
    code = "invalid"
    user_regex = _re.compile(r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*$"
                              r"|^\"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*\"$)",
                              _re.IGNORECASE)
    domain_regex = _re.compile(
        r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)$",
        _re.IGNORECASE,
    )

    def __call__(self, value: str):
        if not value or "@" not in value:
            raise ValidationError(self.message, code=self.code)
        user_part, domain_part = value.rsplit("@", 1)
        if not self.user_regex.match(user_part):
            raise ValidationError(self.message, code=self.code)
        if not self.domain_regex.match(domain_part):
            raise ValidationError(self.message, code=self.code)


class URLValidator:
    schemes = ["http", "https", "ftp", "ftps"]
    message = "Enter a valid URL."
    code = "invalid"

    def __call__(self, value: str):
        if not any(value.startswith(f"{scheme}://") for scheme in self.schemes):
            raise ValidationError(self.message, code=self.code)


class SlugValidator(RegexValidator):
    def __init__(self):
        super().__init__(
            r"^[-a-zA-Z0-9_]+\Z",
            message="Enter a valid slug consisting of letters, numbers, underscores or hyphens.",
            code="invalid",
        )


class UnicodeSlugValidator(RegexValidator):
    def __init__(self):
        super().__init__(
            r"^[-\w]+\Z",
            message="Enter a valid slug.",
            code="invalid",
        )


class DecimalValidator:
    def __init__(self, max_digits: int, decimal_places: int):
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def __call__(self, value):
        import decimal
        try:
            d = decimal.Decimal(value)
        except Exception:
            raise ValidationError("Enter a valid decimal number.", code="invalid") from None
        sign, digits, exponent = d.as_tuple()
        decimals = max(-exponent, 0)
        if decimals > self.decimal_places:
            raise ValidationError(
                f"Ensure that there are no more than {self.decimal_places} decimal places.",
                code="max_decimal_places",
            )
        integer_digits = len(digits) - decimals
        if integer_digits + decimals > self.max_digits:
            raise ValidationError(
                f"Ensure that there are no more than {self.max_digits} digits in total.",
                code="max_digits",
            )


class ProhibitNullCharactersValidator:
    message = "Null characters are not allowed."
    code = "null_characters_not_allowed"

    def __call__(self, value: str):
        if "\x00" in str(value):
            raise ValidationError(self.message, code=self.code)


class BaseValidator:
    """Base class for limit-based validators."""

    message = "Ensure this value is %(limit_value)s (it is %(show_value)s)."
    code = "limit_value"

    def __init__(self, limit_value):
        self.limit_value = limit_value

    def compare(self, a, b) -> bool:
        return a != b

    def clean(self, value):
        return value

    def __call__(self, value):
        cleaned = self.clean(value)
        if self.compare(cleaned, self.limit_value):
            raise ValidationError(
                self.message % {"limit_value": self.limit_value, "show_value": cleaned},
                code=self.code,
                params={"limit_value": self.limit_value, "show_value": cleaned},
            )


class StepValueValidator:
    """Raise ValidationError if value is not a multiple of step from offset."""

    def __init__(self, step: int | float, offset: int | float = 0):
        self.step = step
        self.offset = offset

    def __call__(self, value):
        if value is None:
            return
        try:
            remainder = (float(value) - self.offset) % float(self.step)
            if remainder not in (0, self.step):
                raise ValidationError(
                    f"Ensure this value is a multiple of {self.step}.",
                    code="step_size",
                )
        except (TypeError, ValueError):
            raise ValidationError("Enter a valid number.", code="invalid") from None


def validate_integer(value) -> None:
    """Raise ValidationError if value is not a valid integer."""
    try:
        int(str(value).strip())
    except (ValueError, TypeError):
        raise ValidationError("Enter a valid integer.", code="invalid") from None


def validate_ipv4_address(value: str) -> None:
    """Raise ValidationError if value is not a valid IPv4 address."""
    import ipaddress
    try:
        ipaddress.IPv4Address(value)
    except (ValueError, ipaddress.AddressValueError):
        raise ValidationError("Enter a valid IPv4 address.", code="invalid") from None


def validate_ipv6_address(value: str) -> None:
    """Raise ValidationError if value is not a valid IPv6 address."""
    import ipaddress
    try:
        ipaddress.IPv6Address(value)
    except (ValueError, ipaddress.AddressValueError):
        raise ValidationError("Enter a valid IPv6 address.", code="invalid") from None


def validate_ipv46_address(value: str) -> None:
    """Raise ValidationError if value is not a valid IPv4 or IPv6 address."""
    import ipaddress
    try:
        ipaddress.ip_address(value)
    except (ValueError, ipaddress.AddressValueError):
        raise ValidationError("Enter a valid IP address.", code="invalid") from None


_IMAGE_EXTENSIONS = {
    ".apng", ".avif", ".bmp", ".gif", ".ico", ".jpeg",
    ".jpg", ".png", ".svg", ".tif", ".tiff", ".webp",
}


def validate_image_file_extension(value) -> None:
    """Raise ValidationError if the file is not a recognised image format."""
    import os
    name = getattr(value, "filename", None) or getattr(value, "name", str(value))
    ext = os.path.splitext(str(name))[1].lower()
    if ext not in _IMAGE_EXTENSIONS:
        raise ValidationError(
            f"File extension '{ext}' is not allowed. "
            f"Allowed extensions: {', '.join(sorted(_IMAGE_EXTENSIONS))}.",
            code="invalid_extension",
        )


class FileExtensionValidator:
    """Validate that a file has one of the allowed extensions."""

    def __init__(self, allowed_extensions: list[str]):
        self.allowed_extensions = [e.lower().lstrip(".") for e in allowed_extensions]

    def __call__(self, value) -> None:
        import os
        name = getattr(value, "filename", None) or getattr(value, "name", str(value))
        ext = os.path.splitext(str(name))[1].lower().lstrip(".")
        if ext not in self.allowed_extensions:
            raise ValidationError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed: {', '.join(self.allowed_extensions)}.",
                code="invalid_extension",
            )


def int_list_validator(sep: str = ",", allow_negative: bool = False):
    """Return a validator that accepts a separator-delimited string of integers."""

    class _IntListValidator:
        def __call__(self, value):
            for part in str(value).split(sep):
                stripped = part.strip()
                try:
                    n = int(stripped)
                except ValueError:
                    raise ValidationError(
                        f"'{stripped}' is not a valid integer.", code="invalid"
                    ) from None
                if not allow_negative and n < 0:
                    raise ValidationError("Negative integers are not allowed.", code="invalid")

    return _IntListValidator()


# Convenience singletons
validate_email = EmailValidator()
validate_slug = SlugValidator()
validate_unicode_slug = UnicodeSlugValidator()
validate_url = URLValidator()
