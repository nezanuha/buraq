"""
Functional utilities — lazy objects, cached_property, lazy().

Usage:
    from buraq.utils.functional import cached_property, SimpleLazyObject, lazy
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


class cached_property:  # noqa: N801
    """
    A property that is computed once and cached as an instance attribute.

    Faster than ``@property`` after the first access because the descriptor
    is replaced with the plain value in the instance ``__dict__``.

    Usage:
        class MyModel:
            @cached_property
            def expensive_data(self):
                return compute_something()
    """

    def __init__(self, func: Callable):
        self.func = func
        self.attrname = None
        functools.update_wrapper(self, func)

    def __set_name__(self, owner, name):
        self.attrname = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        name = self.attrname or self.func.__name__
        value = self.func(instance)
        instance.__dict__[name] = value
        return value


class LazyObject:
    """
    Wrap an object that should be created lazily on first access.

    Subclass and override ``_setup()`` to create the wrapped object and
    assign it to ``self._wrapped``.
    """

    _wrapped = None

    def _setup(self):
        raise NotImplementedError

    def __getattr__(self, name):
        if self._wrapped is None:
            self._setup()
        return getattr(self._wrapped, name)

    def __setattr__(self, name, value):
        if name == "_wrapped":
            object.__setattr__(self, name, value)
        elif self._wrapped is None:
            self._setup()
            setattr(self._wrapped, name, value)
        else:
            setattr(self._wrapped, name, value)

    def __delattr__(self, name):
        if self._wrapped is None:
            self._setup()
        delattr(self._wrapped, name)

    def __repr__(self):
        if self._wrapped is None:
            return f"<{self.__class__.__name__}: uninitialized>"
        return repr(self._wrapped)


class SimpleLazyObject(LazyObject):
    """
    Lazily evaluate a callable the first time the object is accessed.

    Usage:
        user = SimpleLazyObject(lambda: get_current_user())
        print(user.username)   # triggers evaluation
    """

    def __init__(self, func: Callable):
        object.__setattr__(self, "_setupfunc", func)
        object.__setattr__(self, "_wrapped", None)

    def _setup(self):
        object.__setattr__(self, "_wrapped", self._setupfunc())

    def __str__(self):
        if self._wrapped is None:
            self._setup()
        return str(self._wrapped)

    def __eq__(self, other):
        if self._wrapped is None:
            self._setup()
        return self._wrapped == other

    def __hash__(self):
        if self._wrapped is None:
            self._setup()
        return hash(self._wrapped)


def lazy(func: Callable, *result_types) -> Callable:
    """
    Return a lazy version of ``func``.

    The result is not computed until it is coerced to one of ``result_types``
    (e.g. str, bytes). Useful for lazy translations and lazy URLs.

    Usage:
        lazy_upper = lazy(str.upper, str)
        title = lazy_upper("hello")
        str(title)   # → "HELLO"
    """

    class _LazyResult:
        def __init__(self, args, kwargs):
            self._args = args
            self._kwargs = kwargs
            self._result = None

        def _resolve(self):
            if self._result is None:
                self._result = func(*self._args, **self._kwargs)
            return self._result

    for rt in result_types:
        if rt is str:
            _LazyResult.__str__ = lambda self: str(self._resolve())
        elif rt is bytes:
            _LazyResult.__bytes__ = lambda self: bytes(self._resolve())

    _LazyResult.__repr__ = lambda self: repr(self._resolve())

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return _LazyResult(args, kwargs)

    return wrapper


def classproperty(func: Callable) -> Any:
    """
    A decorator for class-level properties (no instance needed).

    Usage:
        class MyModel:
            @classproperty
            def table_name(cls):
                return cls.__tablename__
    """

    class _ClassProperty:
        def __init__(self, f):
            self.f = f

        def __get__(self, obj, cls=None):
            return self.f(cls or type(obj))

    return _ClassProperty(func)


__all__ = [
    "cached_property", "LazyObject", "SimpleLazyObject", "lazy", "classproperty",
]
