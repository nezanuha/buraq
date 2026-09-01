"""
@ratelimit() on a view, without importing the application into it.

The only documented way to limit one route was
`@app.state.limiter.limit("5/minute")`, which needs the app at decoration time.
A views module cannot have it: the app builds itself by loading ROOT_URLCONF,
which imports the views, so importing back is circular and the project will not
start. The decorator records the limit and registration applies it, which is the
first moment both the view and the app exist.
"""

import pytest

from buraq.decorators import ratelimit


def test_the_limit_is_recorded_on_the_view():
    @ratelimit("5/minute")
    async def view(request):
        return None

    assert view._ratelimits == ["5/minute"]


def test_the_view_is_returned_unchanged():
    """It is still an ordinary coroutine function until the route is built."""

    async def original(request):
        return None

    assert ratelimit("5/minute")(original) is original


def test_several_limits_at_once():
    @ratelimit("5/minute", "50/day")
    async def view(request):
        return None

    assert view._ratelimits == ["5/minute", "50/day"]


def test_stacking_accumulates():
    """Two decorators should mean two limits, not the last one winning."""

    @ratelimit("50/day")
    @ratelimit("5/minute")
    async def view(request):
        return None

    assert sorted(view._ratelimits) == ["5/minute", "50/day"]


def test_no_limit_is_refused():
    with pytest.raises(ValueError, match="needs a limit"):
        ratelimit()


@pytest.mark.parametrize("bad", ["5 per minute", "", "minute", 5])
def test_something_that_is_not_a_limit_is_refused(bad):
    """Caught here rather than by slowapi at the first request."""
    with pytest.raises(ValueError, match="limits like"):
        ratelimit(bad)


def test_an_undecorated_view_is_left_alone():
    from buraq.urls import _apply_ratelimits

    async def view(request):
        return None

    assert _apply_ratelimits(object(), view) is view


def test_a_limit_with_no_limiter_warns_rather_than_silently_allowing():
    """An unlimited route is the wrong way to discover a missing limiter."""
    from buraq.urls import _apply_ratelimits

    @ratelimit("5/minute")
    async def view(request):
        return None

    class _NoLimiter:
        class state:
            limiter = None

    with pytest.warns(RuntimeWarning, match="no rate limiter"):
        assert _apply_ratelimits(_NoLimiter(), view) is view


def test_the_limiter_is_applied_when_one_exists():
    from buraq.urls import _apply_ratelimits

    applied = []

    class _Limiter:
        def limit(self, spec):
            applied.append(spec)
            return lambda fn: fn

    class _App:
        class state:
            limiter = _Limiter()

    @ratelimit("5/minute", "50/day")
    async def view(request):
        return None

    _apply_ratelimits(_App(), view)
    assert applied == ["5/minute", "50/day"]
