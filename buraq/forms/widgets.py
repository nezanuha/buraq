"""
Form widgets — HTML rendering for form fields.

Usage::

    from buraq.forms.widgets import TextInput

    widget = TextInput(attrs={"class": "form-input"})
    html = widget.render("title", "Hello")
    # → '<input type="text" name="title" value="Hello" class="form-input">'
"""


class Widget:
    """
    Base widget. Subclasses implement ``render()``; ``attrs`` passed to the
    constructor are HTML attributes merged into every render (a caller's
    per-call ``attrs``, such as the ``id`` a bound field supplies, fills in
    anything the widget itself did not already set).
    """

    input_type = "text"

    def __init__(self, attrs: dict = None):
        self.attrs = dict(attrs) if attrs else {}

    def build_attrs(self, attrs: dict = None) -> dict:
        """Merge call-time attrs under the widget's own — the widget's own win on conflicts."""
        return {**(attrs or {}), **self.attrs}

    def render(self, name, value, attrs=None):
        raise NotImplementedError


class TextInput(Widget):
    input_type = "text"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<input type="text" name="{name}" value="{value or ""}"{attr_str}>'


class Textarea(Widget):
    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<textarea name="{name}"{attr_str}>{value or ""}</textarea>'


class FileInput(Widget):
    input_type = "file"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<input type="file" name="{name}"{attr_str}>'


class PasswordInput(Widget):
    """
    Renders ``<input type="password">``.

    ``render_value`` is off by default, so a redisplayed form never echoes a
    submitted password back into the HTML -- where it would reach browser
    history, caches, and any screenshot of the page.
    """

    input_type = "password"

    def __init__(self, attrs: dict = None, render_value: bool = False):
        super().__init__(attrs)
        self.render_value = render_value

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        v = value if self.render_value else ""
        return f'<input type="password" name="{name}" value="{v or ""}"{attr_str}>'


class ChoiceWidget(Widget):
    """Base for widgets backed by a list of ``(value, label)`` choices."""

    def __init__(self, attrs: dict = None, choices: list = None):
        super().__init__(attrs)
        self.choices = list(choices) if choices else []


class Select(ChoiceWidget):
    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        options = ""
        for val, label in self.choices:
            selected = ' selected' if str(val) == str(value) else ''
            options += f'<option value="{val}"{selected}>{label}</option>'
        return f'<select name="{name}"{attr_str}>{options}</select>'


class CheckboxInput(Widget):
    input_type = "checkbox"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        checked = ' checked' if value else ''
        return f'<input type="checkbox" name="{name}"{checked}{attr_str}>'


class NumberInput(Widget):
    input_type = "number"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<input type="number" name="{name}" value="{value or ""}"{attr_str}>'


class URLInput(Widget):
    input_type = "url"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<input type="url" name="{name}" value="{value or ""}"{attr_str}>'


class FormatWidget(Widget):
    """Base for widgets that stringify a date/time value with ``strftime``.

    ``format`` may be passed to the constructor to override the class
    default, the same as ``attrs``::

        DateInput(attrs={"type": "date"}, format="%d/%m/%Y")
    """

    format = ""

    def __init__(self, attrs: dict = None, format: str = None):  # noqa: A002 (the conventional kwarg name)
        super().__init__(attrs)
        if format:
            self.format = format


class DateInput(FormatWidget):
    input_type = "date"
    format = "%Y-%m-%d"

    def render(self, name, value, attrs=None):
        from datetime import date
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        if isinstance(value, date):
            value = value.strftime(self.format)
        return f'<input type="date" name="{name}" value="{value or ""}"{attr_str}>'


class HiddenInput(Widget):
    input_type = "hidden"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        return f'<input type="hidden" name="{name}" value="{value or ""}"{attr_str}>'


class RadioSelect(ChoiceWidget):
    """Renders a list of radio buttons — one per choice."""

    def render(self, name, value, attrs=None):
        # id is per-field, not per-option — an id on every <input> here would
        # duplicate it across the group, so only non-id attrs are repeated.
        item_attrs = {k: v for k, v in self.build_attrs(attrs).items() if k != "id"}
        attr_str = _attrs_to_str(item_attrs)
        items = ""
        for val, label in self.choices:
            checked = ' checked' if str(val) == str(value) else ''
            items += (
                f'<label><input type="radio" name="{name}" value="{val}"'
                f'{checked}{attr_str}> {label}</label>'
            )
        return f'<div class="radio-select">{items}</div>'


class CheckboxSelectMultiple(ChoiceWidget):
    """Renders a list of checkboxes — multiple values may be selected."""

    def render(self, name, value, attrs=None):
        item_attrs = {k: v for k, v in self.build_attrs(attrs).items() if k != "id"}
        attr_str = _attrs_to_str(item_attrs)
        selected = {str(v) for v in (value or [])}
        items = ""
        for val, label in self.choices:
            checked = ' checked' if str(val) in selected else ''
            items += (
                f'<label><input type="checkbox" name="{name}"'
                f' value="{val}"{checked}{attr_str}> {label}</label>'
            )
        return f'<div class="checkbox-select">{items}</div>'


class MultipleHiddenInput(Widget):
    """Renders multiple hidden inputs for a list of values (used by formsets)."""

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        values = value if isinstance(value, (list, tuple)) else [value]
        return "".join(f'<input type="hidden" name="{name}" value="{v}"{attr_str}>' for v in values)


class DateTimeInput(FormatWidget):
    input_type = "datetime-local"
    format = "%Y-%m-%dT%H:%M"

    def render(self, name, value, attrs=None):
        from datetime import datetime
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        if isinstance(value, datetime):
            value = value.strftime(self.format)
        return f'<input type="datetime-local" name="{name}" value="{value or ""}"{attr_str}>'


class TimeInput(FormatWidget):
    input_type = "time"
    format = "%H:%M"

    def render(self, name, value, attrs=None):
        from datetime import time
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        if isinstance(value, time):
            value = value.strftime(self.format)
        return f'<input type="time" name="{name}" value="{value or ""}"{attr_str}>'


class SplitDateTimeWidget(Widget):
    """Renders two inputs: one for date, one for time."""

    def render(self, name, value, attrs=None):
        from datetime import datetime
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        date_val = ""
        time_val = ""
        if isinstance(value, datetime):
            date_val = value.strftime("%Y-%m-%d")
            time_val = value.strftime("%H:%M")
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            date_val, time_val = value[0] or "", value[1] or ""
        return (
            f'<input type="date" name="{name}_date" value="{date_val}"{attr_str}> '
            f'<input type="time" name="{name}_time" value="{time_val}"{attr_str}>'
        )


class SplitHiddenDateTimeWidget(SplitDateTimeWidget):
    """Hidden version of SplitDateTimeWidget."""

    def render(self, name, value, attrs=None):
        from datetime import datetime
        date_val = ""
        time_val = ""
        if isinstance(value, datetime):
            date_val = value.strftime("%Y-%m-%d")
            time_val = value.strftime("%H:%M")
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            date_val, time_val = value[0] or "", value[1] or ""
        return (
            f'<input type="hidden" name="{name}_date" value="{date_val}">'
            f'<input type="hidden" name="{name}_time" value="{time_val}">'
        )


class SelectDateWidget(Widget):
    """Renders three <select> widgets for day, month, and year."""

    def __init__(self, attrs: dict = None, years=None, months=None, empty_label=None):
        super().__init__(attrs)
        import datetime
        current_year = datetime.date.today().year
        self.years = years or list(range(current_year - 10, current_year + 11))
        self.months = months or {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        }
        self.empty_label = empty_label

    def render(self, name, value, attrs=None):
        from datetime import date
        year_val = month_val = day_val = ""
        if isinstance(value, date):
            year_val, month_val, day_val = value.year, value.month, value.day
        year_opts = "".join(
            f'<option value="{y}"{"  selected" if str(y) == str(year_val) else ""}>{y}</option>'
            for y in self.years
        )
        month_opts = "".join(
            f'<option value="{m}"'
            f'{"  selected" if str(m) == str(month_val) else ""}>{label}</option>'
            for m, label in self.months.items()
        )
        day_opts = "".join(
            f'<option value="{d}"{"  selected" if str(d) == str(day_val) else ""}>{d}</option>'
            for d in range(1, 32)
        )
        return (
            f'<select name="{name}_month">{month_opts}</select> '
            f'<select name="{name}_day">{day_opts}</select> '
            f'<select name="{name}_year">{year_opts}</select>'
        )


class NullBooleanSelect(ChoiceWidget):
    """Select widget with Unknown / Yes / No options."""

    def __init__(self, attrs: dict = None):
        super().__init__(attrs, choices=[("unknown", "Unknown"), ("true", "Yes"), ("false", "No")])

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        if value is True or value == "true":
            current = "true"
        elif value is False or value == "false":
            current = "false"
        else:
            current = "unknown"
        opts = "".join(
            f'<option value="{v}"{"  selected" if v == current else ""}>{label}</option>'
            for v, label in self.choices
        )
        return f'<select name="{name}"{attr_str}>{opts}</select>'


class ClearableFileInput(FileInput):
    """File input with a 'clear' checkbox for optional file fields."""

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(self.build_attrs(attrs))
        file_input = f'<input type="file" name="{name}"{attr_str}>'
        if value:
            clear = (
                f'<label>'
                f'<input type="checkbox" name="{name}-clear"> Clear</label> '
                f'<span>Currently: {value}</span>'
            )
            return f"{clear} {file_input}"
        return file_input


class MultiWidget(Widget):
    """
    A widget that is composed of multiple sub-widgets.

    Usage::

        class SplitDateWidget(MultiWidget):
            def __init__(self):
                widgets = [DateInput(), TimeInput()]
                super().__init__(widgets)

            def decompress(self, value):
                if value:
                    return [value.date(), value.time()]
                return [None, None]
    """

    def __init__(self, widgets, attrs: dict = None):
        super().__init__(attrs)
        self.widgets = list(widgets)

    def decompress(self, value):
        return [None] * len(self.widgets)

    def render(self, name, value, attrs=None):
        if value is None:
            value = []
        elif not isinstance(value, (list, tuple)):
            value = self.decompress(value)
        rendered = []
        for i, widget in enumerate(self.widgets):
            val = value[i] if i < len(value) else None
            rendered.append(widget.render(f"{name}_{i}", val, attrs))
        return " ".join(rendered)


def _attrs_to_str(attrs: dict) -> str:
    if not attrs:
        return ""
    return " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())
