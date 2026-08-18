---
title: "Form Validation"
description: "Validate Buraq forms with per-field, async and cross-field rules, plus reusable custom validators — and the order validation runs in."
---

## Validation order

For each field:

1. `field.to_python(value)` — convert raw string to Python type
2. `field.validate(value)` — check required, min/max, etc.
3. `field.run_validators(value)` — run attached validators
4. `form.clean_<fieldname>(value)` — your custom per-field logic

Then once all fields pass:

5. `form.clean()` — cross-field validation

## Per-field validation

Define `clean_<fieldname>` on the form. Must raise `ValidationError` or return the cleaned value:

```python
class PostForm(ModelForm):
    class Meta:
        model  = Post
        fields = ["title", "slug", "content"]

    def clean_slug(self, value):
        if " " in value:
            raise ValidationError("Slug cannot contain spaces.")
        # Check uniqueness
        # (async validators go in clean() below)
        return value.lower()

    def clean_title(self, value):
        return value.strip().title()
```

## Async per-field validation

```python
    async def clean_slug(self, value):
        exists = await Post.objects.filter(slug=value).exists()
        if exists:
            raise ValidationError("A post with this slug already exists.")
        return value
```

## Cross-field validation

`clean()` runs after all fields validate. Use it for rules that involve multiple fields:

```python
    async def clean(self):
        data = self._cleaned_data
        if data.get("is_published") and not data.get("content"):
            self.add_error("content", "Cannot publish a post without content.")
        if data.get("end_date") and data.get("start_date"):
            if data["end_date"] < data["start_date"]:
                self.add_error("end_date", "End date must be after start date.")
        return data
```

## Custom validators (reusable)

```python title="validators.py"
from buraq.exceptions import ValidationError


def validate_no_spaces(value):
    if " " in value:
        raise ValidationError("Value cannot contain spaces.")


def validate_min_words(min_words):
    def inner(value):
        if len(value.split()) < min_words:
            raise ValidationError(f"Must contain at least {min_words} words.")
    return inner
```

Attach to a field:

```python
slug    = CharField(validators=[validate_no_spaces])
content = TextField(validators=[validate_min_words(10)])
```

## Error messages

```python
title = CharField(
    error_messages={
        "required": "Please give your post a title.",
        "max_length": "Title is too long (max 200 characters).",
    }
)
```

## Non-field errors

```python
form.non_field_errors()   # list of errors not tied to a specific field

# Add in clean():
self.add_error(None, "Something went wrong.")   # None = non-field error
# or use the constant:
from buraq.exceptions import NON_FIELD_ERRORS
self.add_error(NON_FIELD_ERRORS, "Something went wrong.")
```
