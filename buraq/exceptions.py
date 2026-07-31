class BuraqException(Exception):
    pass


class ValidationError(BuraqException):
    def __init__(self, message, code=None, params=None):
        self.message = message
        self.code = code or "invalid"
        self.params = params
        super().__init__(message)

    def __str__(self):
        return str(self.message)


class PermissionDenied(BuraqException):
    pass


class SuspiciousOperation(BuraqException):
    pass


class ImproperlyConfigured(BuraqException):
    pass


class ObjectDoesNotExist(BuraqException):
    pass


class MultipleObjectsReturned(BuraqException):
    pass


class FieldError(BuraqException):
    pass


# Sentinel key used in Form.errors for form-level (non-field) errors
NON_FIELD_ERRORS = "__all__"
