# Database Functions

Buraq provides built-in database functions for annotating and filtering querysets. All functions resolve to native SQL — no Python-side processing.

```python
from buraq.orm import functions as Fn
```

---

## Date / Time

### Truncation

Round a datetime down to the nearest unit.

```python
from buraq.orm import functions as Fn

# Group posts by month
posts = await Post.objects.values("author_id").annotate(
    month=Fn.TruncMonth("created_at")
)
```

| Function | SQL equivalent |
|---|---|
| `TruncDate(field)` | `CAST(col AS DATE)` |
| `TruncHour(field)` | `DATE_TRUNC('hour', col)` |
| `TruncDay(field)` | `DATE_TRUNC('day', col)` |
| `TruncWeek(field)` | `DATE_TRUNC('week', col)` |
| `TruncMonth(field)` | `DATE_TRUNC('month', col)` |
| `TruncQuarter(field)` | `DATE_TRUNC('quarter', col)` |
| `TruncYear(field)` | `DATE_TRUNC('year', col)` |

### Extraction

Extract a numeric component from a datetime.

```python
posts = await Post.objects.annotate(year=Fn.ExtractYear("created_at"))
```

| Function | Returns |
|---|---|
| `ExtractYear(field)` | Year as integer |
| `ExtractMonth(field)` | Month (1–12) |
| `ExtractDay(field)` | Day of month |
| `ExtractHour(field)` | Hour (0–23) |
| `ExtractMinute(field)` | Minute |
| `ExtractSecond(field)` | Second |
| `ExtractWeek(field)` | ISO week number |
| `ExtractWeekDay(field)` | Day of week (0 = Sunday) |
| `ExtractQuarter(field)` | Quarter (1–4) |

### Now

```python
# Filter rows created before the current database time
posts = await Post.objects.filter(scheduled_at__lt=Fn.Now())
```

---

## String

```python
from buraq.orm import functions as Fn

# Uppercase
posts = await Post.objects.annotate(upper_title=Fn.Upper("title"))

# Concatenate two columns
posts = await Post.objects.annotate(
    full_name=Fn.Concat("first_name", "last_name")
)

# String length
posts = await Post.objects.annotate(title_len=Fn.Length("title"))
```

| Function | Description |
|---|---|
| `Upper(field)` | Uppercase |
| `Lower(field)` | Lowercase |
| `Length(field)` | Character length |
| `Trim(field)` | Strip both ends |
| `LTrim(field)` | Strip left |
| `RTrim(field)` | Strip right |
| `Reverse(field)` | Reverse string |
| `Concat(*fields)` | Concatenate columns/literals |
| `Replace(field, old, new)` | Replace substring |
| `Substr(field, pos, length)` | Substring extraction |
| `Left(field, n)` | First `n` characters |
| `Right(field, n)` | Last `n` characters |
| `Repeat(field, n)` | Repeat string `n` times |
| `StrIndex(string, substring)` | Position of substring |
| `LPad(field, length, fill)` | Left-pad |
| `RPad(field, length, fill)` | Right-pad |
| `Chr(field)` | Character from ASCII code |
| `Ord(field)` | ASCII code of first character |

---

## Math

```python
posts = await Post.objects.annotate(rounded=Fn.Round("score", 2))
posts = await Post.objects.annotate(abs_val=Fn.Abs("balance"))
```

| Function | Description |
|---|---|
| `Abs(field)` | Absolute value |
| `Ceil(field)` | Ceiling |
| `Floor(field)` | Floor |
| `Round(field, precision=0)` | Round to precision |
| `Sign(field)` | Sign (-1, 0, 1) |
| `Sqrt(field)` | Square root |
| `Log(field, base=10)` | Logarithm |
| `Ln(field)` | Natural log |
| `Mod(field, divisor)` | Modulo |
| `Power(field, exponent)` | Power |
| `Random()` | Random float 0–1 |
| `ACos`, `ASin`, `ATan` | Inverse trig |
| `ATan2(y, x)` | Two-argument arctangent |
| `Cos`, `Sin`, `Tan` | Trig |
| `Degrees`, `Radians` | Angle conversion |

---

## NULL handling

```python
# Return first non-NULL value
posts = await Post.objects.annotate(
    display_name=Fn.Coalesce("nickname", "username")
)

# Greatest / Least across columns
rows = await Product.objects.annotate(best=Fn.Greatest("price", "min_price"))
```

| Function | Description |
|---|---|
| `Coalesce(*fields)` | First non-NULL |
| `NullIf(field, value)` | NULL if equal to value |
| `Greatest(*fields)` | Maximum across columns |
| `Least(*fields)` | Minimum across columns |

---

## Type casting

```python
from buraq.orm import functions as Fn

posts = await Post.objects.annotate(
    int_score=Fn.Cast("score", "int")
)
```

Supported type names: `int`, `float`, `decimal`, `text`, `bool`, `date`, `datetime`, `time`, `uuid`, `json`.

You can also pass a SQLAlchemy type directly:

```python
import sqlalchemy as sa

posts = await Post.objects.annotate(
    score_decimal=Fn.Cast("score", sa.Numeric(10, 2))
)
```

---

## Hash

PostgreSQL only. Requires the `pgcrypto` extension.

```python
users = await User.objects.annotate(pw_hash=Fn.MD5("email"))
```

| Function | Hash |
|---|---|
| `MD5(field)` | MD5 |
| `SHA1(field)` | SHA-1 |
| `SHA256(field)` | SHA-256 |
| `SHA512(field)` | SHA-512 |
