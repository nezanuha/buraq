"""
The counting itself: the rate parser and the in-process backend.

Buraq owns these rather than depending on `limits` for them. The in-process
counter is what nearly every project runs, so it is worth being fast (1.0us
against the library's 16.6us) and worth being correct here rather than one
import away.
"""

import time

import pytest

from buraq.ratelimit import MemoryBackend, Rate, Verdict, parse_rate

# --- parsing ----------------------------------------------------------------


@pytest.mark.parametrize(
    "spec,amount,seconds",
    [
        ("5/minute", 5, 60),
        ("5 per minute", 5, 60),
        ("10/second", 10, 1),
        ("2/hour", 2, 3600),
        ("3/day", 3, 86400),
        ("1/week", 1, 604800),
        ("5/m", 5, 60),
        ("100/h", 100, 3600),
        ("10/5 minutes", 10, 300),
        ("10 per 5 minutes", 10, 300),
        ("  7 / minute  ", 7, 60),
    ],
)
def test_the_forms_a_rate_can_take(spec, amount, seconds):
    assert parse_rate(spec) == Rate(amount, seconds)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "minute",
        "5/",
        "abc",
        "5",
        "/minute",
        "5/fortnight",
        "-1/minute",
        5,
        None,
        ["5/minute"],
    ],
)
def test_something_that_is_not_a_rate_is_refused(bad):
    """Caught where the limit is written, not at the first request."""
    with pytest.raises(ValueError):
        parse_rate(bad)


def test_a_rate_of_zero_is_refused():
    """"0/minute" reads like "no limit" and means "refuse everything". Neither
    reading should be guessed at."""
    with pytest.raises(ValueError, match="at least one call"):
        parse_rate("0/minute")


def test_an_unknown_period_says_which_are_known():
    with pytest.raises(ValueError, match="second, minute, hour, day or week"):
        parse_rate("5/fortnight")


# --- the window -------------------------------------------------------------


def test_a_rate_allows_exactly_its_amount():
    backend = MemoryBackend()
    rate = parse_rate("3/minute")
    assert [bool(backend.hit("k", rate)) for _ in range(4)] == [True, True, True, False]


def test_the_window_moves_rather_than_resetting():
    """
    A fixed window -- what slowapi used -- admits twice the limit across a
    boundary: five at 11:59:59 and five more at 12:00:00. A moving window counts
    the last N seconds from now, so hits have to age out one at a time.
    """
    backend = MemoryBackend()
    rate = parse_rate("3/second")
    [backend.hit("k", rate) for _ in range(3)]

    time.sleep(0.6)
    assert not backend.hit("k", rate), "still inside the window"

    time.sleep(0.5)
    assert backend.hit("k", rate), "the first hits have aged out"


def test_keys_are_counted_apart():
    backend = MemoryBackend()
    rate = parse_rate("2/minute")
    assert [bool(backend.hit("a", rate)) for _ in range(3)] == [True, True, False]
    assert bool(backend.hit("b", rate)) is True


def test_rates_are_counted_apart():
    """
    A view may carry several limits, and they must not share a log. Keyed on the
    caller alone, "5/minute" and "50/day" counted into one place: every call
    spent both, and calls under a loose limit exhausted a tight one that had not
    been reached.

        loose 100/minute, three calls -> [True, True, True]
        tight 2/minute, first call    -> False
    """
    backend = MemoryBackend()
    tight, loose = parse_rate("2/minute"), parse_rate("100/minute")

    assert [bool(backend.hit("k", loose)) for _ in range(3)] == [True] * 3
    assert bool(backend.hit("k", tight)) is True, "the loose limit spent the tight one"
    assert bool(backend.hit("k", tight)) is True
    assert bool(backend.hit("k", tight)) is False, "and now it is genuinely spent"


def test_one_call_spends_one_from_each_limit():
    """Not two from one. A view with two limits is still one call."""
    backend = MemoryBackend()
    a, b = parse_rate("5/minute"), parse_rate("50/day")

    for _ in range(3):
        backend.hit("k", a)
        backend.hit("k", b)

    assert backend.hit("k", a).remaining == 1
    assert backend.hit("k", b).remaining == 46


# --- what the client is told ------------------------------------------------


def test_remaining_counts_down_and_stops_at_zero():
    backend = MemoryBackend()
    rate = parse_rate("3/minute")
    assert [backend.hit("k", rate).remaining for _ in range(4)] == [2, 1, 0, 0]


def test_reset_is_never_zero_while_refused():
    """`Retry-After: 0` invites an immediate retry into the same wall."""
    backend = MemoryBackend()
    rate = parse_rate("1/second")
    backend.hit("k", rate)
    verdict = backend.hit("k", rate)
    assert not verdict
    assert verdict.reset_after >= 1


def test_a_verdict_is_falsey_when_refused():
    """
    Without this a Verdict would be truthy however it came out, and
    `if not await limiter.hit(...)` -- the obvious way to write the check, and
    what the documentation shows -- would silently never limit anything.
    """
    assert bool(Verdict(True, 5, 4, 60)) is True
    assert bool(Verdict(False, 5, 0, 60)) is False
    assert not Verdict(False, 5, 0, 60)


# --- cost -------------------------------------------------------------------


def test_cost_spends_more_of_the_allowance():
    backend = MemoryBackend()
    rate = parse_rate("10/minute")
    assert bool(backend.hit("k", rate, cost=5)) is True
    assert bool(backend.hit("k", rate, cost=5)) is True
    assert bool(backend.hit("k", rate, cost=1)) is False


def test_a_cost_over_the_limit_is_refused_rather_than_wrapping():
    backend = MemoryBackend()
    assert not backend.hit("k", parse_rate("2/minute"), cost=5)


def test_a_refused_call_does_not_spend_anything():
    """A rejected request must not consume allowance, or a client hammering a
    limit could never recover from it."""
    backend = MemoryBackend()
    rate = parse_rate("2/second")
    [backend.hit("k", rate) for _ in range(5)]  # 2 allowed, 3 refused

    time.sleep(1.05)
    assert [bool(backend.hit("k", rate)) for _ in range(2)] == [True, True]


# --- memory -----------------------------------------------------------------


def test_the_number_of_keys_is_bounded():
    """
    The key is usually the caller's address, and an open endpoint sees an
    unbounded number of those. An unbounded dict here is a memory leak that a
    scan or a botnet turns into an outage.
    """
    backend = MemoryBackend(max_keys=100)
    rate = parse_rate("5/minute")
    for i in range(1000):
        backend.hit(f"ip-{i}", rate)

    assert len(backend._log) <= 100


def test_the_key_dropped_is_the_least_recently_used():
    backend = MemoryBackend(max_keys=3)
    rate = parse_rate("5/minute")
    for key in ("a", "b", "c"):
        backend.hit(key, rate)

    backend.hit("a", rate)  # a is now the most recent
    backend.hit("d", rate)  # evicts the least recent, which is b

    seen = {key for key, _rate in backend._log}
    assert "a" in seen
    assert "b" not in seen


def test_expired_hits_do_not_accumulate():
    """The log for one key must not grow without bound either."""
    backend = MemoryBackend()
    rate = parse_rate("100/second")
    for _ in range(50):
        backend.hit("k", rate)
    time.sleep(1.05)
    backend.hit("k", rate)

    assert len(backend._log[("k", rate)]) == 1
