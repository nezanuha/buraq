# Choices

`buraq.utils.choices` provides Django-style enum base classes for defining field choices with labels.

## TextChoices

```python
from buraq.utils.choices import TextChoices

class Status(TextChoices):
    DRAFT     = "draft",     "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED  = "archived",  "Archived"
```

Use in a model field:

```python
from sqlalchemy import Column, String
from buraq.orm.base import Model

class Post(Model):
    status = Column(String, default=Status.DRAFT)
```

## IntegerChoices

```python
from buraq.utils.choices import IntegerChoices

class Priority(IntegerChoices):
    LOW    = 1, "Low"
    MEDIUM = 2, "Medium"
    HIGH   = 3, "High"
```

## Class properties

| Property | Returns |
|---|---|
| `Status.choices` | `[("draft", "Draft"), ("published", "Published"), ...]` |
| `Status.labels` | `["Draft", "Published", "Archived"]` |
| `Status.values` | `["draft", "published", "archived"]` |
| `Status.names` | `["DRAFT", "PUBLISHED", "ARCHIVED"]` |

## Using with form fields

```python
from buraq.forms import ChoiceField

class PostForm(Form):
    status = ChoiceField(choices=Status.choices)
```

## Comparing values

Because `TextChoices` inherits from `str` and `IntegerChoices` from `int`, members compare equal to their raw values:

```python
Status.DRAFT == "draft"   # True
Priority.HIGH == 3        # True
```
