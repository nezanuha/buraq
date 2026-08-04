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


# Convenience singletons
validate_email = EmailValidator()
validate_slug = SlugValidator()
validate_unicode_slug = UnicodeSlugValidator()
validate_url = URLValidator()
