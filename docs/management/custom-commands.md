# Custom Management Commands

Create app-specific commands that run via `buraq manage <command>`.

## Creating a command

```
posts/
└── management/
    ├── __init__.py
    └── commands/
        ├── __init__.py
        └── seed_posts.py
```

```python title="posts/management/commands/seed_posts.py"
from buraq.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the database with sample posts"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10, help="Number of posts to create")
        parser.add_argument("--published", action="store_true", help="Mark posts as published")

    async def handle(self, count=10, published=False, **options):
        from posts.models import Post
        for i in range(count):
            await Post.objects.create(
                title        = f"Sample Post {i + 1}",
                slug         = f"sample-post-{i + 1}",
                content      = f"Content for post {i + 1}.",
                is_published = published,
            )
        self.stdout.write(f"Created {count} posts.")
```

## Running it

```bash
buraq manage seed_posts
buraq manage seed_posts --count 50 --published
```

## BaseCommand API

```python
class Command(BaseCommand):
    help = "Description shown in --help"

    def add_arguments(self, parser):
        # Standard argparse — add arguments here
        parser.add_argument("name", type=str)
        parser.add_argument("--verbose", action="store_true")

    async def handle(self, name, verbose=False, **options):
        # Your logic here — always async
        self.stdout.write(f"Hello, {name}!")
        if verbose:
            self.stdout.write("Verbose mode on.")
```

The `handle()` method is always `async def` — you can `await` anything inside it.
