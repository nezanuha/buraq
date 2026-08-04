class Widget:
    input_type = "text"

    def render(self, name, value, attrs=None):
        raise NotImplementedError


class TextInput(Widget):
    input_type = "text"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        return f'<input type="text" name="{name}" value="{value or ""}"{attr_str}>'


class Textarea(Widget):
    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        return f'<textarea name="{name}"{attr_str}>{value or ""}</textarea>'


class FileInput(Widget):
    input_type = "file"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        return f'<input type="file" name="{name}"{attr_str}>'


class Select(Widget):
    def render(self, name, value, choices=None, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        options = ""
        for val, label in (choices or []):
            selected = ' selected' if str(val) == str(value) else ''
            options += f'<option value="{val}"{selected}>{label}</option>'
        return f'<select name="{name}"{attr_str}>{options}</select>'


class CheckboxInput(Widget):
    input_type = "checkbox"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        checked = ' checked' if value else ''
        return f'<input type="checkbox" name="{name}"{checked}{attr_str}>'


class NumberInput(Widget):
    input_type = "number"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        return f'<input type="number" name="{name}" value="{value or ""}"{attr_str}>'


class URLInput(Widget):
    input_type = "url"

    def render(self, name, value, attrs=None):
        attr_str = _attrs_to_str(attrs or {})
        return f'<input type="url" name="{name}" value="{value or ""}"{attr_str}>'


class DateInput(Widget):
    input_type = "date"
    format = "%Y-%m-%d"

    def render(self, name, value, attrs=None):
        from datetime import date
        attr_str = _attrs_to_str(attrs or {})
        if isinstance(value, date):
            value = value.strftime(self.format)
        return f'<input type="date" name="{name}" value="{value or ""}"{attr_str}>'


class HiddenInput(Widget):
    input_type = "hidden"

    def render(self, name, value, attrs=None):
        return f'<input type="hidden" name="{name}" value="{value or ""}">'


def _attrs_to_str(attrs: dict) -> str:
    if not attrs:
        return ""
    return " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())
