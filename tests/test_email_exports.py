"""
Everything the email documentation tells you to import has to be importable.

`from buraq.contrib.email import get_connection` is the line the page shows, and
it raised ImportError: the function lives in buraq.contrib.email.send and was
never re-exported from the package.
"""

import importlib

import pytest

DOCUMENTED = [
    "EmailMessage",
    "EmailMultiAlternatives",
    "get_connection",
    "send_mail",
    "send_mass_mail",
    "send_template_mail",
    "mail_admins",
    "mail_managers",
]


@pytest.mark.parametrize("name", DOCUMENTED)
def test_the_documented_import_works(name):
    module = importlib.import_module("buraq.contrib.email")
    assert hasattr(module, name), f"from buraq.contrib.email import {name} fails"


def test_all_matches_what_is_importable():
    """__all__ is what `import *` gives and what the audit checks."""
    module = importlib.import_module("buraq.contrib.email")
    assert sorted(module.__all__) == sorted(DOCUMENTED)


def test_a_backend_can_batch():
    """Django opens a connection and sends into it; here the backend takes many.

    There is no connection object to close, so the batching has to be a method
    on the backend rather than a context manager.
    """
    from buraq.contrib.email import get_connection

    assert hasattr(get_connection(), "send_many")
