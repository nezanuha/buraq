# Buraq — Rules for AI Assistants

This file tells AI assistants how this codebase works so they don't introduce wrong patterns.

---

## Core principle: Async-first

Buraq is built on FastAPI + SQLAlchemy async. **Everything that touches I/O must be `async def` and awaited.** There is no sync ORM path. There is no sync-then-async migration path like Django.

---

## Naming rules

### No `a`-prefix methods

Django uses `asave()`, `adelete()`, `aget()`, `apage()`, `asend()` because it added async to an existing sync API and couldn't rename the originals.

**Buraq has no legacy sync API. Do not create `a`-prefix variants.**

| Wrong | Correct |
|---|---|
| `apage()` | `page()` |
| `asend()` | `send()` |
| `asave()` | `save()` |
| `adelete()` | `delete()` |
| `aget()` | `get()` |
| `is_valid_async()` | `is_valid()` |

If a method exists, it is already the async version. One method. One name.

---

## What must be `async def`

| Category | Rule |
|---|---|
| ORM methods (`.all()`, `.get()`, `.create()`, `.update()`, `.delete()`, `.count()`, `.exists()`, `.aggregate()`, `.filter()` terminal) | Always `async def` |
| Model instance methods (`.save()`, `.delete()`, `.refresh_from_db()`) | Always `async def` |
| View functions and CBV handlers (`.get()`, `.post()`, `.dispatch()`) | Always `async def` |
| Form methods that can touch DB (`.is_valid()`, `.save()`, `.clean()`, `clean_<field>()`) | Always `async def` |
| Signal `.send()`, `.send_robust()` | Always `async def` |
| Paginator `.page()` | Always `async def` |
| Cache backend methods (`.get()`, `.set()`, `.delete()`, `.clear()`) | Always `async def` |
| Email backend `.send()` | Always `async def` |
| Session middleware `.dispatch()` | Always `async def` |
| Any custom management command `.handle()` | Always `async def` |

---

## What stays sync (intentionally)

| Category | Reason |
|---|---|
| Validators (`MaxLengthValidator`, `EmailValidator`, etc.) | Pure CPU — no I/O, no await needed |
| Form field `.clean()` / `.to_python()` / `.validate()` | Pure CPU coercion and checks |
| `collect_static()` in staticfiles | CLI-only, runs outside event loop via `asyncio.run()` |
| `StaticFilesHandler.mount()` | Called at app startup, not in request path |
| Signal `.connect()` / `.disconnect()` | No I/O — just list manipulation |
| `Style` methods in `BaseCommand` | String formatting only |
| `Message` / `MessageStorage` in contrib.messages | In-memory only |
| URL registration (`register_urlpatterns`) | Startup-time, not request-path |

---

## Blocking I/O in async functions

Never call blocking I/O directly inside `async def`. Use `asyncio.to_thread()`.

```python
# Wrong — blocks the event loop
async def get(self, key):
    return Path(key).read_text()

# Correct
async def get(self, key):
    return await asyncio.to_thread(Path(key).read_text)
```

This applies to:
- File reads/writes (use `asyncio.to_thread`)
- `subprocess.run()` (use `asyncio.create_subprocess_exec`)
- `time.sleep()` (use `await asyncio.sleep()`)
- Any sync network call (use async client libraries)

---

## ORM usage patterns

```python
# QuerySet — chaining is sync, execution is async
posts = await Post.objects.filter(published=True).order_by("-created_at").limit(10)

# Q objects for complex queries
from buraq.orm.query import Q
posts = await Post.objects.filter(Q(title__contains="hello") | Q(published=True))

# F expressions for field references
await Post.objects.filter(views__gt=F("likes"))

# Aggregation
result = await Post.objects.aggregate(total=Count("id"), avg=Avg("views"))

# Bulk operations
await Post.objects.filter(published=False).delete()  # bulk delete
await Post.objects.filter(author_id=1).update(published=True)  # bulk update

# Instance methods
post = Post(title="Hello")
await post.save()
await post.delete()
await post.refresh_from_db()
```

---

## Forms

```python
class PostForm(ModelForm):
    class Meta:
        model = Post
        fields = ["title", "content"]

    async def clean_title(self):      # can be async
        title = self.cleaned_data["title"]
        if await Post.objects.filter(title=title).exists():
            raise ValidationError("Title already taken.")
        return title

    async def clean(self):            # can be async
        return self.cleaned_data

# In views — always await is_valid() and save()
form = PostForm(data=dict(await request.form()))
if await form.is_valid():
    post = await form.save()
```

---

## Signals

```python
from buraq.signals import post_save

@post_save.connect
async def on_save(sender, instance, created, **kwargs):  # can be sync or async
    if created:
        await send_welcome_email(instance)

# Send manually
await my_signal.send(sender=MyModel, instance=obj)
```

---

## Paginator

```python
paginator = Paginator(Post.objects.filter(published=True), per_page=10)
page = await paginator.page(1)   # always await — works with QuerySets and lists

for post in page:
    print(post.title)

page.has_next()
page.has_previous()
paginator.num_pages
```

---

## Transactions

```python
from buraq.db import atomic

# Context manager
async with atomic():
    post = await Post.objects.create(title="Hello")
    await Tag.objects.create(name="python")

# Decorator
@atomic
async def create_with_tags(title, tags):
    post = await Post.objects.create(title=title)
    await post.tags.add(*tags)
```

---

## Class-based views

```python
from buraq.views import ListView, DetailView, CreateView

class PostListView(ListView):
    model = Post
    template_name = "posts/list.html"
    paginate_by = 10

    async def get_queryset(self):          # override is async
        return await Post.objects.filter(published=True)

# Register in urls.py — as_view() returns an async function
get("/", PostListView.as_view(), name="post_list")
```

---

## Custom management commands

```python
# myapp/management/commands/my_command.py
from buraq.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description of what this does"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10)

    async def handle(self, *args, **options):   # always async def
        count = options["count"]
        self.stdout.write(self.style.SUCCESS(f"Done: {count}"))
```

Run with: `python manage.py manage my_command --count=5`

---

## Architecture summary

```
buraq/
├── orm/           # SQLAlchemy 2.0 async ORM
│   ├── fields.py  # Django-like field declarations → SA columns
│   ├── base.py    # Model base with __init_subclass__ magic
│   ├── manager.py # QuerySet + Manager (all async terminal methods)
│   ├── query.py   # Q objects, F expressions
│   └── aggregates.py  # Count, Sum, Avg, Min, Max
├── forms/         # Form + ModelForm (is_valid async, save async)
├── views/         # CBVs (all handlers async)
├── signals.py     # Signal (send async)
├── paginator.py   # Paginator (page async)
├── decorators.py  # login_required etc (wrappers are async)
├── shortcuts.py   # render, redirect, get_object_or_404
├── validators.py  # Sync only — CPU validators
├── exceptions.py  # ValidationError, PermissionDenied etc
├── db/
│   └── transaction.py  # atomic() — async context manager + decorator
└── contrib/
    ├── auth/      # JWT auth, User model
    ├── admin/     # SQLAdmin auto-admin
    ├── cache/     # memory / redis / file backends (all async)
    ├── email/     # smtp / console / file backends (all async)
    ├── messages/  # Flash messages (in-memory, sync OK)
    ├── sessions/  # Cookie sessions middleware (async)
    └── staticfiles/  # Static file serving + collectstatic
```

---

## Checklist before adding any new function

- [ ] Does it touch a database? → `async def`, use `SessionLocal()`
- [ ] Does it touch the filesystem at request time? → `async def` + `asyncio.to_thread()`
- [ ] Does it touch a network (redis, smtp, etc.)? → `async def`, use async client
- [ ] Is it pure CPU/memory? → `def` is fine, but `async def` is also OK
- [ ] Does it have a Django `a`-prefix equivalent (like `apage`)? → Do NOT add the prefix, just write the async version with the normal name
- [ ] Is the new method called inside an existing `async def`? → Must `await` it
