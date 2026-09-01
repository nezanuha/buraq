"""
Rate limiting, owned rather than depended on.

This replaced slowapi, and with it the ``limits`` library for the default path.
The in-process counter is the one nearly every project runs, it is small enough
to be worth getting right here, and owning it means the common case carries no
dependency at all.

The distributed counter is a different matter: doing check-and-increment
atomically across processes is where rate limiters go subtly wrong, and that
correctness is worth more than the dependency. ``RATE_LIMIT_STORAGE`` still
hands that job to ``limits``, which is optional and only imported when a project
asks for a shared store.

The algorithm here is a moving window over a log of hit times. A fixed window --
what slowapi used, and what most naive implementations do -- admits twice the
limit across a boundary: five at 11:59:59 and five more at 12:00:00.
"""
from __future__ import annotations

import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

__all__ = ["Rate", "MemoryBackend", "Verdict", "parse_rate"]

_UNITS = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "s": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "m": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "h": 3600,
    "day": 86400,
    "days": 86400,
    "d": 86400,
    "week": 604800,
    "weeks": 604800,
    "w": 604800,
}

# "5/minute", "5 per minute", "10/5 minutes", "100 per hour"
_RATE = re.compile(
    r"^\s*(\d+)\s*(?:/|\s+per\s+)\s*(\d*)\s*([a-z]+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Rate:
    """A parsed limit: ``amount`` hits per ``seconds``."""

    amount: int
    seconds: int

    def __str__(self) -> str:
        return f"{self.amount}/{self.seconds}s"


@dataclass(frozen=True, slots=True)
class Verdict:
    """The outcome of one check, and what to tell the client about it."""

    allowed: bool
    limit: int
    remaining: int
    reset_after: int
    """Whole seconds until the window has room again. Never 0 while blocked --
    a `Retry-After: 0` invites an immediate retry into the same wall."""

    def __bool__(self) -> bool:
        """True when the call was allowed.

        Without this a Verdict would be truthy however it came out, and
        ``if not await limiter.hit(...)`` -- the obvious way to write a check,
        and what the documentation shows -- would silently never limit anything.
        """
        return self.allowed


def parse_rate(rate: str) -> Rate:
    """Parse ``"5/minute"``, ``"5 per minute"``, ``"10/5 minutes"``.

    Raises ``ValueError`` for anything else, at the moment the limit is written
    rather than at the first request that would have been checked against it.
    """
    if not isinstance(rate, str):
        raise ValueError(f"a rate looks like '5/minute', not {rate!r}")
    match = _RATE.match(rate)
    if not match:
        raise ValueError(f"a rate looks like '5/minute', not {rate!r}")

    amount, multiple, unit = match.groups()
    seconds = _UNITS.get(unit.lower())
    if seconds is None:
        raise ValueError(
            f"{unit!r} is not a period. Use second, minute, hour, day or week."
        )
    if int(amount) < 1:
        raise ValueError(f"a rate has to allow at least one call, not {rate!r}")

    return Rate(int(amount), seconds * int(multiple or 1))


class MemoryBackend:
    """Counters for this process, in a bounded LRU of hit logs.

    Bounded because the key is usually the caller's address, and an open
    endpoint sees an unbounded number of those: an unbounded dict here is a
    memory leak that a scan or a botnet turns into an outage. Once ``max_keys``
    is reached the least recently touched key is dropped, which at worst forgives
    a caller who has not been seen in a while.
    """

    __slots__ = ("_log", "_max_keys")

    def __init__(self, max_keys: int = 100_000):
        # Keyed on (key, rate), not key alone: a view may carry several limits,
        # and "5/minute" and "50/day" counting into one log would make every
        # call spend both -- three calls under a loose limit exhausting a tight
        # one that had not been reached.
        self._log: OrderedDict[tuple[str, Rate], deque[float]] = OrderedDict()
        self._max_keys = max_keys

    def hit(self, key: str, rate: Rate, cost: int = 1) -> Verdict:
        """Count ``cost`` against ``key``, and say whether it was allowed."""
        now = time.monotonic()
        cutoff = now - rate.seconds
        slot = (key, rate)

        log = self._log.get(slot)
        if log is None:
            log = self._log[slot] = deque()
        else:
            self._log.move_to_end(slot)

        # Hits leave in the order they arrived, so stopping at the first one
        # still inside the window is enough.
        while log and log[0] <= cutoff:
            log.popleft()

        if len(log) + cost > rate.amount:
            # log[0] is the oldest hit still counted; room appears when it ages
            # out. ceil, so a client waiting exactly this long succeeds.
            reset = max(1, int(log[0] - cutoff + 0.999)) if log else 1
            return Verdict(False, rate.amount, 0, reset)

        log.extend([now] * cost)
        if len(self._log) > self._max_keys:
            self._log.popitem(last=False)

        remaining = rate.amount - len(log)
        reset = max(1, int(log[0] - cutoff + 0.999)) if log else rate.seconds
        return Verdict(True, rate.amount, remaining, reset)

    def clear(self) -> None:
        self._log.clear()
