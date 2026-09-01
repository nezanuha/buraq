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
from buraq.ratelimit import Verdict


def test_the_limit_is_recorded_on_the_view():
    @ratelimit("5/minute")
    async def view(request):
        return None

    assert view._ratelimits == [("5/minute", "ip", 1, None)]


def test_the_view_is_returned_unchanged():
    """It is still an ordinary coroutine function until the route is built."""

    async def original(request):
        return None

    assert ratelimit("5/minute")(original) is original


def test_several_limits_at_once():
    @ratelimit("5/minute", "50/day")
    async def view(request):
        return None

    assert view._ratelimits == [("5/minute", "ip", 1, None), ("50/day", "ip", 1, None)]


def test_stacking_accumulates():
    """Two decorators should mean two limits, not the last one winning."""

    @ratelimit("50/day")
    @ratelimit("5/minute")
    async def view(request):
        return None

    assert sorted(view._ratelimits) == [
        ("5/minute", "ip", 1, None),
        ("50/day", "ip", 1, None),
    ]


def test_no_limit_is_refused():
    with pytest.raises(ValueError, match="needs a limit"):
        ratelimit()


@pytest.mark.parametrize("bad", ["", "minute", "abc", "5/", 5])
def test_something_that_is_not_a_limit_is_refused(bad):
    """Caught here rather than by slowapi at the first request."""
    with pytest.raises(ValueError, match="limits like"):
        ratelimit(bad)


@pytest.mark.parametrize("good", ["5/minute", "5 per minute", "10/second", "2/hour"])
def test_every_form_the_parser_accepts_is_accepted(good):
    """
    Validation asks `limits.parse`, not a rule of our own. A look-for-a-slash
    check got this wrong in both directions: it passed "5/", which is not a
    limit, and rejected "5 per minute", which is one -- and which RATE_LIMIT,
    parsed by the same library, accepted. The two spellings now agree.
    """

    @ratelimit(good)
    async def view(request):
        return None

    assert view._ratelimits == [(good, "ip", 1, None)]


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


@pytest.mark.asyncio
async def test_every_limit_on_the_view_is_checked():
    """All of them, not just the first -- @ratelimit("5/minute", "50/day")
    means both apply."""
    from buraq.urls import _apply_ratelimits

    checked = []

    class _Limiter:
        async def check(self, rate, key, cost=1):
            checked.append(str(rate))
            return Verdict(True, rate.amount, rate.amount - 1, rate.seconds)

    class _App:
        class state:
            limiter = _Limiter()

    class _Request:
        scope = {"headers": [], "client": ("1.2.3.4", 1)}

    @ratelimit("5/minute", "50/day")
    async def view(request):
        return "body"

    limited = _apply_ratelimits(_App(), view)
    assert await limited(request=_Request()) == "body"
    assert checked == ["5/60s", "50/86400s"]


@pytest.mark.asyncio
async def test_the_view_does_not_run_once_the_limit_is_hit():
    """A limited view that still executes has not been limited."""
    from fastapi import HTTPException

    from buraq.urls import _apply_ratelimits

    ran = []

    class _Limiter:
        async def check(self, rate, key, cost=1):
            return Verdict(False, rate.amount, 0, rate.seconds)

    class _App:
        class state:
            limiter = _Limiter()

    class _Request:
        scope = {"headers": [], "client": ("1.2.3.4", 1)}

    @ratelimit("5/minute")
    async def view(request):
        ran.append(True)
        return "body"

    limited = _apply_ratelimits(_App(), view)
    with pytest.raises(HTTPException) as caught:
        await limited(request=_Request())

    assert caught.value.status_code == 429
    assert caught.value.headers["Retry-After"] == "60"
    assert ran == [], "the view ran anyway"


@pytest.mark.asyncio
async def test_the_signature_survives_wrapping():
    """FastAPI reads the signature to inject parameters, and _inject_request
    reads it after this wrapper is applied."""
    import inspect

    from buraq.urls import _apply_ratelimits

    class _App:
        class state:
            class limiter:
                @staticmethod
                async def check(rate, key, cost=1):
                    return Verdict(True, rate.amount, 1, rate.seconds)

    @ratelimit("5/minute")
    async def view(request, pk: int):
        return None

    limited = _apply_ratelimits(_App(), view)
    assert list(inspect.signature(limited).parameters) == ["request", "pk"]


# --- key= -------------------------------------------------------------------


def test_the_default_key_is_the_address():
    @ratelimit("5/minute")
    async def view(request):
        return None

    assert view._ratelimits == [("5/minute", "ip", 1, None)]


def test_a_key_of_user_is_recorded():
    @ratelimit("5/minute", key="user")
    async def view(request):
        return None

    assert view._ratelimits == [("5/minute", "user", 1, None)]


def test_something_that_is_not_a_key_is_refused():
    with pytest.raises(ValueError, match="takes 'ip', 'user', or a function"):
        ratelimit("5/minute", key="ipaddress")


def _request(user=None, ip="1.2.3.4"):
    class _Request:
        scope = {"headers": [], "client": (ip, 1), "user": user}

    return _Request()


class _User:
    is_authenticated = True

    def __init__(self, pk):
        self.pk = pk


def test_a_signed_in_user_is_counted_by_identity_not_address():
    """
    An office behind one address is a single IP. Limiting a signed-in action by
    address rations it across everyone there at once, and lets a user reset
    their own allowance by changing networks.
    """
    from buraq.urls import _keyfunc

    by_user = _keyfunc("user")
    assert by_user(_request(_User(7), ip="10.0.0.1")) == by_user(
        _request(_User(7), ip="10.0.0.2")
    ), "the same user from two addresses is one client"
    assert by_user(_request(_User(7))) != by_user(_request(_User(8))), (
        "two users behind one address are two clients"
    )


def test_an_anonymous_request_falls_back_to_the_address():
    """Anonymous callers have no identity to count, and must not share one
    bucket -- the first of them would lock out all the rest."""
    from buraq.urls import _keyfunc

    class _Anon:
        is_authenticated = False
        pk = None

    by_user = _keyfunc("user")
    assert by_user(_request(_Anon(), ip="10.0.0.1")) == "10.0.0.1"
    assert by_user(_request(None, ip="10.0.0.2")) == "10.0.0.2"


def test_a_user_key_cannot_collide_with_an_address():
    """Without a prefix, the user whose pk is 12 and a caller from the address
    "12" would share a counter."""
    from buraq.urls import _keyfunc

    by_user = _keyfunc("user")
    assert by_user(_request(_User(12))) != by_user(_request(None, ip="12"))


def test_a_callable_key_gets_the_request():
    from buraq.urls import _keyfunc

    keyfunc = _keyfunc(lambda r: f"tenant:{r.scope['client'][0]}")
    assert keyfunc(_request(ip="9.9.9.9")) == "tenant:9.9.9.9"
