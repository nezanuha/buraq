"""
`@admin.register(Model)` is the form most people reach for first.

It did not exist. buraq.contrib.admin exported ModelAdmin, AdminSite and site
and nothing else, so a scaffolded app -- which used the decorator -- raised
AttributeError on import and could not be loaded at all.
"""

import pytest

from buraq.contrib import admin
from buraq.orm import fields
from buraq.orm.base import Model


def _model(name):
    return type(name, (Model,), {
        "__app_label__": "admin_register_test",
        "title": fields.CharField(max_length=50),
    })


def test_the_decorator_registers_and_returns_the_class():
    thing = _model("RegDecorated")

    @admin.register(thing)
    class ThingAdmin(admin.ModelAdmin):
        list_display = ("id", "title")

    assert thing in admin.site._registry
    assert ThingAdmin.__name__ == "ThingAdmin", "the decorator must return the class"


def test_it_takes_several_models():
    first, second = _model("RegFirst"), _model("RegSecond")

    @admin.register(first, second)
    class BothAdmin(admin.ModelAdmin):
        pass

    assert first in admin.site._registry
    assert second in admin.site._registry


def test_site_register_still_works():
    """The explicit call is the other documented form and must keep working."""
    thing = _model("RegExplicit")

    class ThingAdmin(admin.ModelAdmin):
        pass

    admin.site.register(thing, ThingAdmin)
    assert thing in admin.site._registry


def test_no_model_is_an_error():
    with pytest.raises(ValueError, match="at least one model"):
        admin.register()


def test_a_class_that_is_not_a_modeladmin_is_refused():
    """Otherwise it registers and fails later, when the page is opened."""
    thing = _model("RegNotAdmin")
    with pytest.raises(TypeError, match="ModelAdmin"):
        admin.register(thing)(type("NotAnAdmin", (), {}))


def test_a_site_that_is_not_an_adminsite_is_refused():
    thing = _model("RegBadSite")
    with pytest.raises(TypeError, match="AdminSite"):
        admin.register(thing, site=object())
