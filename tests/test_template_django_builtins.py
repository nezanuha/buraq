"""
The built-ins a template ported from Django reaches for.

Buraq renders with Jinja2, so most of Django's *tags* are Jinja's own -- `for`,
`if`, `block`, `extends`, `include`, `with`, `filter` -- and its *filters* are
what Buraq has to supply. Fifty-one of Django's fifty-seven were already here.
These are the rest, plus three tags Jinja has no answer for.

`get_digit` is the one that was present but unreachable: it was registered as
`getdigit`, so the name a Django template actually writes raised an error.
"""

import pytest
from jinja2 import Environment

from buraq.template.builtins import register_builtins


@pytest.fixture
def env():
    environment = Environment(autoescape=True)
    register_builtins(environment)
    return environment


def render(env, template, **context):
    return env.from_string(template).render(**context)


# --- add ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "template,expected",
    [
        ("{{ 4|add(6) }}", "10"),
        ("{{ '4'|add('6') }}", "10"),
        ("{{ 'a'|add('b') }}", "ab"),
        ("{{ [1]|add([2]) }}", "[1, 2]"),
    ],
)
def test_add_adds_numbers_and_joins_anything_else(env, template, expected):
    assert render(env, template) == expected


def test_add_returns_empty_when_neither_applies(env):
    """A template is a poor place to discover a type error, which is why Django
    swallows it here rather than raising mid-page."""
    assert render(env, "{{ v|add(1) }}", v={"a": 1}) == ""


# --- divisibleby -------------------------------------------------------------


@pytest.mark.parametrize(
    "value,arg,expected",
    [(9, 3, "True"), (10, 3, "False"), (0, 3, "True"), (9, 0, "False")],
)
def test_divisibleby(env, value, arg, expected):
    """Jinja has this as a test -- `n is divisibleby(3)` -- but not as a filter,
    and a template ported from Django writes the filter."""
    assert render(env, "{{ v|divisibleby(a) }}", v=value, a=arg) == expected


# --- stringformat ------------------------------------------------------------


@pytest.mark.parametrize(
    "value,spec,expected",
    [(5, "03d", "005"), (3.14159, ".2f", "3.14"), (255, "x", "ff"), ("hi", "s", "hi")],
)
def test_stringformat(env, value, spec, expected):
    """Django's spelling leaves off the leading %, since it would end the tag."""
    assert render(env, "{{ v|stringformat(s) }}", v=value, s=spec) == expected


def test_a_format_that_does_not_apply_gives_empty(env):
    assert render(env, "{{ v|stringformat('d') }}", v="not a number") == ""


# --- get_digit ---------------------------------------------------------------


def test_get_digit_is_reachable_by_the_name_django_uses(env):
    """It was registered as `getdigit`, so `get_digit` -- what a ported template
    writes -- was simply not there."""
    assert render(env, "{{ 123456789|get_digit(2) }}") == "8"


def test_the_old_spelling_still_works(env):
    assert render(env, "{{ 123456789|getdigit(2) }}") == "8"


# --- escapeseq and safeseq ---------------------------------------------------


def test_escapeseq_escapes_each_item(env):
    """Escaping the joined string instead would escape the separators too."""
    assert render(env, "{{ v|escapeseq|join(', ') }}", v=["<b>", "&"]) == "&lt;b&gt;, &amp;"


def test_escapeseq_does_not_escape_twice(env):
    """Its results are marked safe, as Django's escape does. Plain strings would
    be escaped again on the way out, and `<b>` would render `&amp;lt;b&amp;gt;`."""
    assert "&amp;lt;" not in render(env, "{{ v|escapeseq|join('') }}", v=["<b>"])


def test_safeseq_marks_each_item_safe(env):
    """Marking the list safe says nothing about its items, which is what the
    join actually escapes."""
    assert render(env, "{{ v|safeseq|join(', ') }}", v=["<b>", "x"]) == "<b>, x"


def test_a_list_marked_safe_without_safeseq_still_escapes_its_items(env):
    """The reason safeseq exists."""
    assert render(env, "{{ v|join(', ') }}", v=["<b>"]) == "&lt;b&gt;"


# --- firstof -----------------------------------------------------------------


def test_firstof_takes_the_first_truthy_value(env):
    assert render(env, "{{ firstof(a, b, c) }}", a="", b=None, c="third") == "third"


def test_firstof_falls_back_to_a_default(env):
    assert render(env, "{{ firstof(a, b, default='none') }}", a="", b=0) == "none"


def test_firstof_beats_chained_defaults(env):
    """Jinja's `|default` only catches undefined, not the empty string -- which
    is what a missing form value or a blank field actually is."""
    assert render(env, "{{ firstof(a, b) }}", a="", b="second") == "second"


# --- widthratio --------------------------------------------------------------


@pytest.mark.parametrize(
    "value,maximum,width,expected",
    [(175, 200, 100, "88"), (0, 200, 100, "0"), (200, 200, 100, "100")],
)
def test_widthratio(env, value, maximum, width, expected):
    assert render(env, "{{ widthratio(v, m, w) }}", v=value, m=maximum, w=width) == expected


def test_widthratio_of_an_empty_dataset_is_zero_not_an_error(env):
    """An empty dataset is a normal thing to hand a template, and a page that
    renders nothing beats one that 500s."""
    assert render(env, "{{ widthratio(1, 0, 100) }}") == "0"


# --- querystring -------------------------------------------------------------


class _Request:
    """Enough of a request for the query string."""

    def __init__(self, items):
        self._items = items

    @property
    def query_params(self):
        items = self._items

        class _Params:
            @staticmethod
            def multi_items():
                return list(items)

        return _Params()


@pytest.fixture
def request_with_filters():
    return _Request([("q", "shoes"), ("tag", "red"), ("tag", "blue"), ("page", "1")])


def test_querystring_keeps_what_is_there_and_changes_one(env, request_with_filters):
    """Paging without losing the filters the visitor already chose, which is
    otherwise a rebuild of the whole string by hand."""
    result = render(env, "{{ querystring(request, page=2) }}", request=request_with_filters)
    assert result == "?q=shoes&amp;tag=red&amp;tag=blue&amp;page=2"


def test_querystring_drops_a_parameter_set_to_none(env, request_with_filters):
    result = render(env, "{{ querystring(request, tag=None) }}", request=request_with_filters)
    assert result == "?q=shoes&amp;page=1"


def test_querystring_repeats_a_parameter_given_a_list(env, request_with_filters):
    """For the checkbox-style filters that set one name several times."""
    result = render(
        env, "{{ querystring(request, tag=['a','b']) }}", request=request_with_filters
    )
    assert result == "?q=shoes&amp;page=1&amp;tag=a&amp;tag=b"


def test_querystring_with_no_request_is_empty(env):
    """Rendered outside a request -- an email, a management command -- rather
    than raising."""
    assert render(env, "{{ querystring() }}") == ""


def test_querystring_with_nothing_to_add_is_empty(env):
    assert render(env, "{{ querystring(request) }}", request=_Request([])) == ""


# --- the whole set -----------------------------------------------------------


def test_every_django_filter_has_an_answer(env):
    """
    Django's built-in filters, against what a Buraq template can reach -- Jinja's
    own included, since `lower`, `join` and `length` are already there under the
    same names.

    `load` and `templatetag` are absent by design: Jinja has no tag libraries to
    load, and no `{%` to escape, so neither has anything to do here.
    """
    django_filters = {
        "add", "addslashes", "capfirst", "center", "cut", "date", "default",
        "default_if_none", "dictsort", "dictsortreversed", "divisibleby", "escape",
        "escapejs", "escapeseq", "filesizeformat", "first", "floatformat",
        "force_escape", "get_digit", "iriencode", "join", "json_script", "last",
        "length", "linebreaks", "linebreaksbr", "linenumbers", "ljust", "lower",
        "make_list", "phone2numeric", "pluralize", "pprint", "random", "rjust",
        "safe", "safeseq", "slice", "slugify", "stringformat", "striptags", "time",
        "timesince", "timeuntil", "title", "truncatechars", "truncatechars_html",
        "truncatewords", "truncatewords_html", "unordered_list", "upper",
        "urlencode", "urlize", "urlizetrunc", "wordcount", "wordwrap", "yesno",
    }
    available = set(env.filters) | set(env.globals)

    assert not (django_filters - available)


# --- cycle -------------------------------------------------------------------


def test_cycle_rendered_directly_gives_a_value_not_a_repr(env):
    """
    `{{ cycle("a", "b") }}` is the obvious translation of Django's
    `{% cycle %}`, and it used to put `<_Cycle object at 0x...>` into the page.
    No error, no warning -- that, in the HTML.
    """
    assert render(env, '{{ cycle("a", "b") }}') == "a"


def test_cycle_kept_in_a_variable_advances_on_each_call(env):
    """The form the docstring documents, for cycling across a loop."""
    template = '{% set c = cycle("a", "b") %}{% for i in range(4) %}{{ c() }}{% endfor %}'
    assert render(env, template) == "abab"


def test_jinjas_own_loop_cycle_is_the_answer_inside_a_loop(env):
    """Calling `cycle()` fresh on each iteration would build a new one every
    time and always return the first value, so this is what the documentation
    points at."""
    template = '{% for i in range(4) %}{{ loop.cycle("odd", "even") }} {% endfor %}'
    assert render(env, template) == "odd even odd even "


# --- the Django-to-Jinja table in the documentation --------------------------


@pytest.mark.parametrize(
    "template,expected",
    [
        # Filter arguments are call parentheses, not a colon.
        ('{% for i in [7, 8] %}{{ loop.index }}{% endfor %}', "12"),
        ('{% for i in [7, 8] %}{{ loop.index0 }}{% endfor %}', "01"),
        ('{% for i in [7, 8] %}{{ loop.revindex }}{% endfor %}', "21"),
        # Django's {% empty %} is Jinja's {% else %}.
        ("{% for i in [] %}x{% else %}none{% endfor %}", "none"),
        # Django's {% comment %} is {# #}, and {% verbatim %} is {% raw %}.
        ("{# hidden #}ok", "ok"),
        ("{% raw %}{{ x }}{% endraw %}", "{{ x }}"),
        # A missing variable renders empty, as in Django.
        ("[{{ missing }}]", "[]"),
    ],
)
def test_the_documented_translations_render_as_documented(env, template, expected):
    """The table is only worth having if each row is true."""
    assert render(env, template) == expected


def test_strict_undefined_turns_a_typo_into_an_error():
    """What the documentation offers for projects that would rather not have a
    misspelled variable render as nothing."""
    from jinja2 import Environment as JinjaEnvironment
    from jinja2 import StrictUndefined, UndefinedError

    strict = JinjaEnvironment(undefined=StrictUndefined)
    with pytest.raises(UndefinedError):
        strict.from_string("{{ nope }}").render()
