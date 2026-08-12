"""
Data structures — MultiValueDict and ImmutableList.

Usage:
    from buraq.utils.datastructures import MultiValueDict

    d = MultiValueDict({"a": [1, 2, 3]})
    d["a"]           # → 3  (last value, Django behaviour)
    d.getlist("a")   # → [1, 2, 3]
    d.getfirst("a")  # → 1
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class MultiValueDict(dict):
    """
    A dict subclass that can hold multiple values per key.

    This behaves like a regular dict for single-value access (returns the
    *last* value for a key), but provides ``getlist()`` to retrieve all values.

    Primarily used for HTML form data where a field may appear multiple times.

    Usage:
        d = MultiValueDict({"colors": ["red", "green", "blue"]})
        d["colors"]            # → "blue"   (last value)
        d.getlist("colors")    # → ["red", "green", "blue"]
        d.getfirst("colors")   # → "red"
        d.setlist("colors", ["cyan", "magenta"])
    """

    def __init__(self, key_to_list_mapping: dict | None = None):
        super().__init__()
        if key_to_list_mapping:
            for key, value in key_to_list_mapping.items():
                if isinstance(value, list):
                    super().__setitem__(key, value)
                else:
                    super().__setitem__(key, [value])

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, [value])

    def __getitem__(self, key: str) -> Any:
        values = super().__getitem__(key)
        return values[-1] if values else None

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key: str, default: list | None = None) -> list:
        """Return all values for *key* as a list."""
        try:
            return list(super().__getitem__(key))
        except KeyError:
            return default if default is not None else []

    def getfirst(self, key: str, default: Any = None) -> Any:
        """Return the first value for *key*."""
        values = super().get(key, [])
        return values[0] if values else default

    def setlist(self, key: str, list_: list) -> None:
        """Set all values for *key* at once."""
        super().__setitem__(key, list(list_))

    def appendlist(self, key: str, value: Any) -> None:
        """Append *value* to the list of values for *key*."""
        current = super().get(key, [])
        current.append(value)
        super().__setitem__(key, current)

    def items(self) -> Iterator[tuple[str, Any]]:  # type: ignore[override]
        """Yield (key, last_value) pairs — same as dict.items() behaviour."""
        for key, values in super().items():
            yield key, values[-1] if values else None

    def lists(self) -> Iterator[tuple[str, list]]:
        """Yield (key, [all_values]) pairs."""
        yield from super().items()

    def values(self) -> Iterator[Any]:  # type: ignore[override]
        for values in super().values():
            yield values[-1] if values else None

    def copy(self) -> MultiValueDict:
        result = MultiValueDict()
        for key, values in super().items():
            result.setlist(key, list(values))
        return result

    def update(self, other: dict | None = None, **kwargs) -> None:  # type: ignore[override]
        if other:
            if isinstance(other, MultiValueDict):
                for key, values in other.lists():
                    self.setlist(key, values)
            else:
                for key, value in other.items():
                    self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def __repr__(self) -> str:
        return f"<MultiValueDict: {dict(self.lists())}>"
