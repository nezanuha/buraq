# Translatable Models

`buraq.contrib.i18n.models` provides `TranslatableModel` and `TranslatedFields` — store per-language field values in a companion database table, fully async, with no extra dependencies.

---

## Design

### Why a separate translation table?

There are three common ways to store translated fields. Buraq uses the **separate table** pattern — the industry standard for i18n ORMs:

| Pattern | How | Trade-off |
|---|---|---|
| **Separate table** (Buraq) | `article_translation(master_id, language_code, title)` | Clean schema, best for many languages, single indexed lookup per request — the industry standard |
| JSON column | `articles.translations JSONB {"en": {...}, "ar": {...}}` | One row per object; harder to query / index individual language fields |
| EAV | `translations(object_id, field_name, language, value)` | Fully flexible; terrible read performance (many joins per field) |

The separate-table pattern wins for frameworks: queries are predictable, the schema is explicit, and Alembic can diff it like any other table.

### Performance

Each `get_translation()` call issues a single query on `(master_id, language_code)`. The `UNIQUE` constraint on that pair doubles as a B-tree index — PostgreSQL and MySQL use it automatically. No joins, no subqueries, no N+1 risk beyond what you'd have fetching the parent object.

All methods are `async def` throughout — no sync blocking anywhere in the translation path.

---

## How it works

Declaring `translations = TranslatedFields(...)` on a model causes Buraq to automatically create a `{table}_translation` companion table with:

- `id` — auto PK
- `master_id` — FK → parent table (`CASCADE DELETE`)
- `language_code` — e.g. `"en"`, `"ar"`, `"fr"`
- One column per field declared in `TranslatedFields`
- `UNIQUE(master_id, language_code)` — one row per language per object

The translation model is a standard SQLAlchemy model registered with `Base.metadata`, so Alembic detects it like any other model — no extra migration configuration needed.

---

## Usage

```python
from buraq import models
from buraq.contrib.i18n.models import TranslatableModel, TranslatedFields

class Article(TranslatableModel):
    slug       = models.SlugField(unique=True)
    author_id  = models.ForeignKey("buraq_users")
    created_at = models.DateTimeField(auto_now_add=True)

    translations = TranslatedFields(
        title   = models.CharField(max_length=255),
        content = models.TextField(),
    )
```

This auto-creates two tables:

```
articles                         articles_translation
──────────────────────────────   ──────────────────────────────────────────────────
id   slug          author_id     id   master_id   language_code   title    content
1    hello-world   7             1    1            en              Hello    ...
                                 2    1            ar              مرحبا    ...
```

---

## Migrations

```bash
buraq makemigrations
buraq migrate
```

Both tables are detected and migrated together — nothing extra to configure.

---

## Reading translations

### get_translation()

Returns the translation row for the given language. Defaults to the active language set by `LocaleMiddleware`.

```python
article = await Article.objects.get(slug="hello-world")

# Active language (from LocaleMiddleware / URL prefix)
tr = await article.get_translation()
print(tr.title)

# Explicit language
tr = await article.get_translation("ar")
print(tr.title)   # "مرحبا بالعالم"
```

Raises `Article.translation_model.DoesNotExist` if no translation exists for that language.

### safe_translation_getter()

Returns a field value with optional fallback — never raises:

```python
# Returns None if translation missing
title = await article.safe_translation_getter("title", language_code="ar")

# Falls back to English if Arabic translation is missing
title = await article.safe_translation_getter(
    "title",
    language_code="ar",
    fallback_language="en",
)

# Custom default value
title = await article.safe_translation_getter(
    "title",
    language_code="fr",
    default="(untranslated)",
)
```

---

## Writing translations

### set_translation()

Upsert — creates the row if it doesn't exist, updates it otherwise:

```python
await article.set_translation("en", title="Hello World", content="...")
await article.set_translation("ar", title="مرحبا بالعالم", content="...")
```

---

## Listing and deleting translations

```python
# All translations for an article
translations = await article.get_translations()
for tr in translations:
    print(tr.language_code, tr.title)

# Delete one language
await article.delete_translation("fr")
```

---

## In views

`get_translation()` without arguments reads the active language from `LocaleMiddleware` — no extra wiring needed:

```python
from buraq.shortcuts import render
from myapp.models import Article

async def article_detail(request, slug: str):
    article = await Article.objects.get(slug=slug)
    tr = await article.get_translation()   # active language from URL prefix
    return render(request, "article_detail.html", {"article": article, "tr": tr})
```

---

## In templates

```html+jinja
<h1>{{ tr.title }}</h1>
<div>{{ tr.content }}</div>
```

---

## Querying the translation table directly

The auto-created model is available as `Model.translation_model`:

```python
# All Arabic translations across all articles
arabic = await Article.translation_model.objects.filter(language_code="ar")

# Check if a specific translation exists
exists = await Article.translation_model.objects.filter(
    master_id=article.id,
    language_code="fr",
).exists()
```

---

## Reference

### TranslatedFields

```python
TranslatedFields(**fields: Field)
```

Accepts any Buraq model field. Assign it once per model as a class attribute — the attribute name doesn't matter (`translations` is conventional).

### TranslatableModel methods

| Method | Description |
|---|---|
| `await get_translation(language_code=None)` | Fetch one translation row; raises `DoesNotExist` if missing |
| `await safe_translation_getter(field, *, language_code, default, fallback_language)` | Fetch a field value, never raises |
| `await set_translation(language_code, **fields)` | Upsert a translation row |
| `await get_translations()` | All translation rows for this instance |
| `await delete_translation(language_code)` | Delete one translation row |

### Translation model

| Attribute | Description |
|---|---|
| `Model.translation_model` | The auto-created SQLAlchemy model class |
| `Model.translation_model.objects` | Full ORM `Manager` — supports `filter()`, `get()`, `all()`, etc. |
| `Model._translated_field_names` | List of field names stored in the translation table |
