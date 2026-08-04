# Timezone

Buraq's timezone utilities mirror `django.utils.timezone` and use Python's stdlib `zoneinfo` module (a C extension, no extra dependencies). Language state is stored in a `contextvars.ContextVar` making it async-safe — each request gets its own timezone context.

---

## Setup

```python
# settings.py
USE_TZ = True          # enable timezone-aware datetimes (default: True)
TIME_ZONE = "UTC"      # default timezone
```

!!! tip
    Always keep `USE_TZ = True`. Store datetimes in UTC in the database and convert to local time only when displaying to users.

---

## Usage

```python
from buraq.utils.timezone import (
    now,
    localtime,
    localdate,
    make_aware,
    make_naive,
    is_aware,
    is_naive,
    get_current_timezone,
    activate,
    deactivate,
    override,
    UTC,
)
```

---

## now()

Return the current datetime. With `USE_TZ = True` (default) returns an aware UTC datetime.

```python
from buraq.utils.timezone import now

dt = now()
# datetime(2026, 8, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)
```

Use `now()` instead of `datetime.now()` in your models and views — it respects `USE_TZ`.

---

## localtime()

Convert a UTC datetime to the active (or specified) timezone.

```python
from buraq.utils.timezone import now, localtime
from zoneinfo import ZoneInfo

utc_dt = now()

# Convert to the active timezone (from TIME_ZONE setting)
local = localtime(utc_dt)

# Convert to a specific timezone
riyadh = localtime(utc_dt, "Asia/Riyadh")
tokyo  = localtime(utc_dt, ZoneInfo("Asia/Tokyo"))

# No argument → current time in active timezone
local_now = localtime()
```

---

## localdate()

Return the local date (not datetime) for a given UTC datetime.

```python
from buraq.utils.timezone import now, localdate

today = localdate()                           # today in active timezone
date  = localdate(post.created_at, "Asia/Dubai")
```

---

## make_aware() / make_naive()

```python
from datetime import datetime
from buraq.utils.timezone import make_aware, make_naive

# Attach timezone info to a naive datetime
naive = datetime(2026, 8, 4, 12, 0, 0)
aware = make_aware(naive)                          # uses active timezone
aware = make_aware(naive, "America/New_York")      # explicit timezone

# Strip timezone info (convert first, then strip)
naive_local = make_naive(aware)                    # in active timezone
naive_ny    = make_naive(aware, "America/New_York")
```

---

## is_aware() / is_naive()

```python
from datetime import datetime, timezone
from buraq.utils.timezone import is_aware, is_naive

aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
naive = datetime(2026, 1, 1)

is_aware(aware)   # True
is_naive(naive)   # True
```

---

## override() — per-request timezone

Use the `override` context manager to temporarily activate a different timezone. Pairs well with user timezone preferences:

```python
from buraq.utils.timezone import override, localtime, now
from buraq.shortcuts import render

async def dashboard(request):
    user_tz = request.user.timezone or "UTC"   # e.g. "America/Chicago"

    with override(user_tz):
        context = {
            "now": localtime(),
            "joined": localtime(request.user.created_at),
        }

    return render(request, "dashboard.html", context)
```

Works identically in sync and async code because it uses `contextvars`.

---

## activate() / deactivate()

Lower-level API — use `override()` instead when possible.

```python
from buraq.utils.timezone import activate, deactivate

token = activate("Asia/Karachi")
# ... timezone is now Asia/Karachi ...
deactivate(token)  # restore previous timezone
```

---

## UTC constant

```python
from buraq.utils.timezone import UTC
from datetime import datetime

dt = datetime(2026, 8, 4, 12, 0, 0, tzinfo=UTC)
```

---

## Settings Reference

| Setting | Default | Description |
|---|---|---|
| `USE_TZ` | `True` | Store and return timezone-aware datetimes |
| `TIME_ZONE` | `"UTC"` | Default timezone (any IANA tz name, e.g. `"America/New_York"`) |

Valid timezone strings follow the [IANA timezone database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) — for example: `"Europe/London"`, `"Asia/Tokyo"`, `"America/New_York"`.
