"""
Form widget rendering.

Regression context: `Widget` had no `__init__`, so the constructor call shown
in its own docs — `TextInput(attrs={"class": "form-input"})` — raised
`TypeError: TextInput() takes no arguments`. Even past that, nothing wired a
widget instance's `attrs` into `render()`, `Field` defaulted `self.widget` to
a bare `{}` instead of a widget instance, `BoundField.__str__` returned the
raw value instead of rendering the widget (so `{{ form.field }}` in a
template printed plain text), and three field types (`TextField`,
`PasswordField`, `HiddenField`) marked themselves with a string
(`widget = "textarea"`) that nothing actually read. `ModelForm.Meta.widgets`
was accepted but silently ignored for auto-generated fields.

Also covered here: `BaseForm.fields` used to return a fresh dict wrapping the
same shared `Field`/`Widget` objects on every access, so mutating a bound
field's widget in one form instance (e.g. `self.fields["slug"].widget.attrs
["readonly"] = True`, a pattern used to lock the slug on edit) leaked into
every other instance of that form class, including unrelated requests.
"""

from buraq import forms
from buraq.forms.fields import Field
from buraq.forms.widgets import (
    CheckboxInput,
    DateInput,
    HiddenInput,
    PasswordInput,
    Select,
    Textarea,
    TextInput,
)


def test_widget_attrs_constructor_matches_the_documented_example():
    """docs/topics/forms/widgets.md's own "rendering a widget manually" example."""
    widget = TextInput(attrs={"class": "form-input"})
    html = widget.render("title", "Hello")
    assert html == '<input type="text" name="title" value="Hello" class="form-input">'


def test_render_time_attrs_fill_in_around_constructor_attrs():
    widget = TextInput(attrs={"class": "input"})
    html = widget.render("title", "Hello", attrs={"id": "id_title"})
    assert 'class="input"' in html
    assert 'id="id_title"' in html


def test_constructor_attrs_win_over_render_time_on_conflict():
    """A widget's own attrs take priority — mirrors Django's build_attrs()."""
    widget = TextInput(attrs={"id": "custom-id"})
    html = widget.render("title", "Hello", attrs={"id": "id_title"})
    assert 'id="custom-id"' in html
    assert 'id="id_title"' not in html


def test_date_widget_accepts_a_format_override():
    import datetime

    widget = DateInput(attrs={"class": "input"}, format="%d/%m/%Y")
    html = widget.render("dob", datetime.date(2026, 1, 5))
    assert 'value="05/01/2026"' in html
    assert 'class="input"' in html


def test_field_gets_a_real_widget_instance_by_default():
    field = Field()
    assert isinstance(field.widget, TextInput)


def test_widget_class_passed_as_a_class_is_instantiated():
    """docs/topics/forms/widgets.md: `content = fields.CharField(widget=Textarea)`."""
    field = forms.CharField(widget=Textarea)
    assert isinstance(field.widget, Textarea)


def test_field_default_widgets_match_the_docs_table():
    assert isinstance(forms.TextField().widget, Textarea)
    assert isinstance(forms.PasswordField().widget, PasswordInput)
    assert isinstance(forms.HiddenField().widget, HiddenInput)
    assert isinstance(forms.BooleanField(required=False).widget, CheckboxInput)
    assert isinstance(forms.ChoiceField(choices=[("a", "A")]).widget, Select)


def test_choicefield_choices_propagate_to_the_widget():
    field = forms.ChoiceField(choices=[("a", "A"), ("b", "B")])
    assert field.widget.choices == [("a", "A"), ("b", "B")]


def test_bound_field_str_renders_the_widget_not_the_raw_value():
    class DemoForm(forms.Form):
        name = forms.CharField(widget=TextInput(attrs={"class": "input"}))

    bound = DemoForm(data={"name": "Ada"})["name"]
    html = str(bound)
    assert html.startswith("<input")
    assert 'value="Ada"' in html
    assert 'class="input"' in html


def test_bound_field_str_includes_the_auto_id():
    class DemoForm(forms.Form):
        name = forms.CharField()

    html = str(DemoForm()["name"])
    assert 'id="id_name"' in html


def test_password_widget_never_echoes_the_submitted_value():
    class LoginForm(forms.Form):
        password = forms.CharField(widget=PasswordInput())

    html = str(LoginForm(data={"password": "hunter2"})["password"])
    assert "hunter2" not in html


def test_hidden_and_visible_fields_are_classified_by_widget_type():
    class DemoForm(forms.Form):
        name = forms.CharField()
        token = forms.HiddenField()

    f = DemoForm()
    assert [bf.name for bf in f.hidden_fields()] == ["token"]
    assert [bf.name for bf in f.visible_fields()] == ["name"]


def test_mutating_one_instances_widget_does_not_leak_into_another():
    """Regression: self.fields[...] used to alias the class-level Field objects."""
    class DemoForm(forms.Form):
        slug = forms.CharField(widget=TextInput(attrs={"class": "input"}))

    first = DemoForm()
    first.fields["slug"].widget.attrs["readonly"] = True
    second = DemoForm()

    assert first.fields["slug"].widget.attrs.get("readonly") is True
    assert "readonly" not in second.fields["slug"].widget.attrs
    assert "readonly" not in str(second["slug"])


def test_modelform_meta_widgets_applies_to_auto_generated_fields():
    from buraq import models

    class WidgetDemoModel(models.Model):
        title = models.CharField(max_length=100)
        is_active = models.BooleanField(default=True)

    class DemoForm(forms.ModelForm):
        class Meta:
            model = WidgetDemoModel
            fields = ["title", "is_active"]
            widgets = {
                "title": forms.TextInput(attrs={"class": "input"}),
                "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
            }

    f = DemoForm()
    assert isinstance(f.fields["title"].widget, TextInput)
    assert f.fields["title"].widget.attrs == {"class": "input"}
    assert isinstance(f.fields["is_active"].widget, CheckboxInput)
