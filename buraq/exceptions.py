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


class SuspiciousFileOperation(SuspiciousOperation):
    pass


class SuspiciousMultipartForm(SuspiciousOperation):
    pass


class ImproperlyConfigured(BuraqException):
    pass


class ObjectDoesNotExist(BuraqException):
    pass


class MultipleObjectsReturned(BuraqException):
    pass


class FieldError(BuraqException):
    pass


class FieldDoesNotExist(BuraqException):
    pass


class NoReverseMatch(BuraqException):
    pass


class Resolver404(BuraqException):
    pass


class ViewDoesNotExist(BuraqException):
    pass


class MiddlewareNotUsed(BuraqException):
    pass


class AppRegistryNotReady(BuraqException):
    pass


class EmptyResultSet(BuraqException):
    pass


class FullResultSet(BuraqException):
    pass


class BadRequest(BuraqException):
    pass


class DisallowedHost(SuspiciousOperation):
    pass


class DisallowedRedirect(SuspiciousOperation):
    pass


class RequestAborted(BuraqException):
    pass


class TooManyFieldsSent(SuspiciousOperation):
    pass


class RequestDataTooBig(SuspiciousOperation):
    pass


class InvalidSessionKey(SuspiciousOperation):
    pass


class TooManyFilesSent(SuspiciousOperation):
    pass


# Sentinel key used in Form.errors for form-level (non-field) errors
NON_FIELD_ERRORS = "__all__"
