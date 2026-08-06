# Humanize

`buraq.contrib.humanize` provides human-readable formatting helpers for numbers, dates, and durations.

```python
from buraq.contrib.humanize import intcomma, naturaltime, ordinal
```

## Numbers

### intcomma

Format integers with thousands separators:

```python
intcomma(1234567)      # → "1,234,567"
intcomma(1000)         # → "1,000"
intcomma(999)          # → "999"
```

### intword

Convert large integers to a friendly string:

```python
intword(1_200_000)     # → "1.2 million"
intword(2_500_000_000) # → "2.5 billion"
intword(3_000_000_000_000) # → "3.0 trillion"
intword(500)           # → "500"
```

### ordinal

Return the ordinal string for an integer:

```python
ordinal(1)    # → "1st"
ordinal(2)    # → "2nd"
ordinal(3)    # → "3rd"
ordinal(11)   # → "11th"
ordinal(21)   # → "21st"
```

### apnumber

Convert small numbers to AP style words (numbers 10+ returned as digits):

```python
apnumber(0)   # → "zero"
apnumber(1)   # → "one"
apnumber(9)   # → "nine"
apnumber(10)  # → "10"
apnumber(100) # → "100"
```

### pluralize

Return a plural suffix based on a count:

```python
count = 3
f"You have {count} message{pluralize(count)}."
# → "You have 3 messages."

count = 1
f"You have {count} message{pluralize(count)}."
# → "You have 1 message."

# Custom singular/plural
f"Found {count} {pluralize(count, 'match', 'matches')}."
```

## Dates

### naturalday

Return "today", "yesterday", or "tomorrow" for close dates; otherwise format:

```python
from datetime import date, timedelta

naturalday(date.today())                    # → "today"
naturalday(date.today() - timedelta(days=1))  # → "yesterday"
naturalday(date.today() + timedelta(days=1))  # → "tomorrow"
naturalday(date(2024, 6, 15))               # → "Jun 15"
naturalday(date(2024, 6, 15), "%d %B %Y")  # → "15 June 2024"
```

### naturaltime

Return a human-readable relative time:

```python
from datetime import datetime, timedelta

naturaltime(datetime.now() - timedelta(seconds=5))    # → "just now"
naturaltime(datetime.now() - timedelta(minutes=2))    # → "2 minutes ago"
naturaltime(datetime.now() - timedelta(hours=3))      # → "3 hours ago"
naturaltime(datetime.now() - timedelta(days=1))       # → "1 day ago"
naturaltime(datetime.now() + timedelta(hours=1))      # → "1 hour from now"
naturaltime(datetime.now() + timedelta(days=7))       # → "7 days from now"
```

### naturalduration

Format a `timedelta` as a readable string:

```python
from datetime import timedelta

naturalduration(timedelta(hours=1, minutes=30))  # → "1 hour, 30 minutes"
naturalduration(timedelta(days=2, hours=3))      # → "2 days, 3 hours"
naturalduration(timedelta(seconds=45))           # → "45 seconds"
naturalduration(timedelta(0))                    # → "0 seconds"
```

## In templates

All helpers work in Jinja2 templates when passed via context:

```python
from buraq.contrib.humanize import intcomma, naturaltime

async def post_detail(request, pk: int):
    post = await Post.objects.get(id=pk)
    return templates.TemplateResponse(request, "post/detail.html", {
        "post": post,
        "views": intcomma(post.views),
        "published": naturaltime(post.published_at),
    })
```
