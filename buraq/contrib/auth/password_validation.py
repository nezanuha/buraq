"""
Password validators — enforce password strength policies.

Usage in settings:
    AUTH_PASSWORD_VALIDATORS = [
        {"NAME": "buraq.contrib.auth.password_validation.MinimumLengthValidator",
         "OPTIONS": {"min_length": 8}},
        {"NAME": "buraq.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "buraq.contrib.auth.password_validation.NumericPasswordValidator"},
        {"NAME": "buraq.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    ]

Usage:
    from buraq.contrib.auth.password_validation import validate_password
    validate_password("mypassword", user=request.user)
"""
from __future__ import annotations

import importlib
import unicodedata

from buraq.exceptions import ValidationError


def validate_password(password: str, user=None, password_validators=None) -> None:
    """
    Run all configured password validators against ``password``.
    Raises ValidationError listing all failures.
    """
    errors = []
    for validator in get_password_validators(password_validators):
        try:
            validator.validate(password, user)
        except ValidationError as e:
            errors.append(str(e))
    if errors:
        raise ValidationError(errors)


def get_password_validators(validator_configs=None):
    """Instantiate validators from config list or settings.AUTH_PASSWORD_VALIDATORS."""
    if validator_configs is None:
        from buraq.conf import settings
        validator_configs = getattr(settings, "AUTH_PASSWORD_VALIDATORS", [])
    validators = []
    for config in validator_configs:
        path = config["NAME"]
        options = config.get("OPTIONS", {})
        module_path, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        validators.append(cls(**options))
    return validators


class MinimumLengthValidator:
    """Reject passwords shorter than min_length characters."""

    def __init__(self, min_length: int = 8):
        self.min_length = min_length

    def validate(self, password: str, user=None) -> None:
        if len(password) < self.min_length:
            raise ValidationError(
                f"This password is too short."
                f" It must contain at least {self.min_length} characters."
            )

    def get_help_text(self) -> str:
        return f"Your password must contain at least {self.min_length} characters."


class CommonPasswordValidator:
    """Reject passwords that appear in a common-password list."""

    # A curated subset of the most common passwords. Production deployments should
    # supply a larger list via the passwords_list_path option.
    COMMON_PASSWORDS = frozenset({
        "password", "123456", "password1", "12345678", "111111", "1234567",
        "sunshine", "qwerty", "iloveyou", "princess", "admin", "welcome",
        "666666", "abc123", "football", "123123", "monkey", "654321",
        "superman", "master", "shadow", "dragon", "pass", "letmein",
        "michael", "qwerty123", "123456789", "1234567890", "000000",
    })

    def __init__(self, passwords_list_path: str | None = None):
        if passwords_list_path:
            import pathlib
            self._extra = frozenset(
                p.strip().lower()
                for p in pathlib.Path(passwords_list_path).read_text().splitlines()
                if p.strip()
            )
        else:
            self._extra = frozenset()

    def validate(self, password: str, user=None) -> None:
        if password.lower() in self.COMMON_PASSWORDS or password.lower() in self._extra:
            raise ValidationError("This password is too common.")

    def get_help_text(self) -> str:
        return "Your password can't be a commonly used password."


class NumericPasswordValidator:
    """Reject passwords that consist entirely of digits."""

    def validate(self, password: str, user=None) -> None:
        if password.isdigit():
            raise ValidationError("This password is entirely numeric.")

    def get_help_text(self) -> str:
        return "Your password can't be entirely numeric."


class UserAttributeSimilarityValidator:
    """Reject passwords that are too similar to user attributes (username, email, etc.)."""

    def __init__(
        self,
        user_attributes: list[str] | None = None,
        max_similarity: float = 0.7,
    ):
        self.user_attributes = user_attributes or ["username", "first_name", "last_name", "email"]
        self.max_similarity = max_similarity

    def validate(self, password: str, user=None) -> None:
        if user is None:
            return
        password_lower = password.lower()
        for attr in self.user_attributes:
            value = getattr(user, attr, None)
            if not value:
                continue
            value_str = str(value).lower()
            if not value_str:
                continue
            # Normalize unicode characters before comparison.
            value_str = unicodedata.normalize("NFKD", value_str)
            similarity = self._similarity(password_lower, value_str)
            if similarity >= self.max_similarity:
                raise ValidationError(
                    f"The password is too similar to the {attr.replace('_', ' ')}."
                )

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Return a simple longest-common-substring similarity ratio."""
        if not a or not b:
            return 0.0
        longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
        if shorter in longer:
            return len(shorter) / len(longer)
        # SequenceMatcher-style ratio approximation.
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()

    def get_help_text(self) -> str:
        return "Your password can't be too similar to your other personal information."


class MaximumLengthValidator:
    """Reject passwords longer than max_length characters (guards against DoS via bcrypt)."""

    def __init__(self, max_length: int = 4096):
        self.max_length = max_length

    def validate(self, password: str, user=None) -> None:
        if len(password) > self.max_length:
            raise ValidationError(
                f"This password is too long. It must contain at most {self.max_length} characters."
            )

    def get_help_text(self) -> str:
        return f"Your password must contain at most {self.max_length} characters."
