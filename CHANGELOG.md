# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Viewsets and a router.** `ModelViewSet` states a model once and `Router`
  turns it into the five routes a JSON resource needs, with names, response
  models and the fixed paths registered before the one carrying a converter:

  ```python
  class PostViewSet(ModelViewSet):
      model = Post
      read_schema = PostRead
      write_schema = PostCreate

  router = Router()
  router.register("/api/posts", PostViewSet, basename="post")
  urlpatterns = router.urls
  ```

  Only the actions a class defines are routed, so a read-only resource is one
  with `create`, `update` and `destroy` removed — there is no second list of
  permitted methods to keep in step. Overriding an action keeps its route.
- **Declarative filtering on a viewset** — `filter_fields`, `search_fields`,
  `ordering_fields`, `ordering` and `paginate_by` map `?status=draft`,
  `?search=hello`, `?ordering=-created_at` and `?page=2` onto the queryset. A
  parameter naming a field the class did not offer is ignored rather than
  reaching a column it was never meant to.

- **`startapp` writes an `apps.py`.** `AppConfig` and its `ready()` hook exist
  and the apps documentation says to create the file — but the scaffold never
  did, so a startup hook was reachable only by someone who had read that page
  and knew the file was theirs to add. The generated one says it is optional,
  shows the `INSTALLED_APPS` entry that activates it, and has an empty `ready()`
  to fill in.
- **`startproject` writes a `tests/` directory with one passing test.**
  `pyproject.toml` already pointed pytest at `tests`, and nothing created it, so
  the first `buraq test` on a new project reported `collected 0 items` and
  exited 0 — which reads like a broken runner rather than like there is nowhere
  to look. It now reports `1 passed`, and the example shows how to drive the
  application with `TestClient`.

- **A Schemas page, and a `schemas.py` that introduces itself.** `buraq startapp`
  writes a `schemas.py` with a `PostRead`
  and a `PostCreate` in it, and nothing explained what they were for — one line
  in a directory listing was the whole of it. The page covers why the two
  directions are separate classes, what `from_attributes` is doing and which
  schema needs it, how a schema keeps a model field like `created_at` out of a
  response, that a JSON endpoint needs `@csrf_exempt` because CSRF expects a
  form token, and when not to write one at all. The generated file now opens
  with a docstring saying the same in three lines — what it is, that an app
  serving only HTML can delete it, and where the rest is — so the question does
  not have to be asked before it can be answered.

- **`@admin.register(Model)`** — registering a `ModelAdmin` where the class is,
  rather than in a call underneath it. It is the form most people reach for
  first, which is how it went unnoticed that it did not exist: the scaffolded
  `admin.py` used it, so every generated app raised `AttributeError` on import.
  It takes several models, returns the class, and refuses a class that is not a
  `ModelAdmin` rather than failing later when the page is opened.
  `site.register(Model, AdminClass)` is unchanged and remains the way to
  register with the default admin.

- **Every setting is documented.** `STATIC_DIR` — which a scaffolded project has
  in its settings file — and `CACHE_MEMCACHED_SERVERS` appeared on no
  documentation page. All 95 settings now do.

- **CI runs the suite against PostgreSQL and MySQL**, not only SQLite. The
  differences that actually bite — sequences, locking, collation, what a driver
  accepts — are the ones SQLite cannot show, so passing on it proved less than
  it appeared to. Two jobs, Linux only, since service containers do not run on
  the Windows or macOS images.

  This needed the suite to be portable first: `tests/test_auth.py` and
  `tests/test_auth_permissions.py` set `DATABASE_URL` to in-memory SQLite
  themselves, so they would have gone on testing SQLite whatever CI configured.
  They now use the database under test, and changing `DATABASE_URL` mid-suite
  forgets the cached engine rather than leaving queries pointed at the old one.

- **`OPTIONS` for the database connection.** Anything SQLAlchemy's engine or the
  driver accepts can now be set, per database, without Buraq needing a named
  setting for each:

  ```python
  DATABASES = {
      "default": {
          "URL": "postgresql+asyncpg://user:pass@primary/db",
          "OPTIONS": {"pool_size": 20, "connect_args": {"statement_cache_size": 0}},
      },
  }
  DATABASE_OPTIONS = {...}   # the same, for the DATABASE_URL form
  ```

  This was a deployment blocker rather than a convenience: asyncpg behind
  PgBouncer in transaction mode needs `statement_cache_size=0` or its prepared
  statements break, and there was no way to say so. SQLite's `timeout` and the
  isolation level had the same problem. `connect_args` is merged with what Buraq
  sets rather than replacing it, so SQLite's `check_same_thread` survives an
  entry of your own. A plain URL string stays valid wherever a mapping is
  accepted.
- **`DATABASE_POOL_RECYCLE`**, defaulting to an hour. MySQL closes an idle
  connection after eight; `pool_pre_ping` only discovered that by paying a round
  trip on checkout, where recycling retires the connection before it goes stale.
- **MariaDB** named in the driver check, so a URL without an async driver
  suggests `mariadb+aiomysql` rather than falling through unrecognised.
- **A Databases page** covering which other databases are reachable at all —
  CockroachDB, YugabyteDB and TiDB through wire compatibility, SQL Server
  through `aioodbc`, and Oracle, Firebird, Spanner and Snowflake not at all,
  because SQLAlchemy 2.0 exposes no async dialect for them — and what each
  supported backend does differently — SQLite
  dropping `FOR UPDATE` from the statement rather than raising, MySQL refusing to
  index a `TEXT` column or a `unique` `VARCHAR` past 255 characters, PgBouncer,
  isolation levels — and saying plainly that the test suite runs against SQLite
  only.

- **Several databases, and reads from a replica.** `DATABASES` names them, each
  a URL like `DATABASE_URL` so the async driver still has somewhere to live:

  ```python
  DATABASES = {
      "default": "postgresql+asyncpg://user:pass@primary/db",
      "replica": "postgresql+asyncpg://user:pass@replica/db",
  }
  DATABASE_READ_REPLICAS = ["replica"]
  ```

  Queries do not change: reads go to a replica, writes to `default`. Reads
  *inside* `atomic()` also go to `default` — a replica lags the primary, so a
  transaction that writes a row and reads it back must not be answered by one.
  `QuerySet.using()` names a database outright and overrides both; it previously
  existed only to raise `NotImplementedError`. `DATABASE_URL` remains the
  single-database form and is unchanged.

  There are no database routers: nothing decides per model or per app where a
  query belongs, and migrations only run against `default`. A replica named in
  `DATABASE_READ_REPLICAS` but absent from `DATABASES` is reported as a
  configuration error rather than failing later as a query against a database
  the project thought it had.

- **`DATABASE_URL` is checked for an async driver at startup.** A blocking one —
  or none at all — now raises `ImproperlyConfigured` naming the driver to use and
  the extra that installs it. SQLAlchemy caught these already, but a bare
  `postgresql://` surfaced as `ModuleNotFoundError: No module named 'psycopg2'`,
  which reads like a missing dependency and sends you to install the one package
  that cannot help.

- **Static files are compressed once, not on every request** — `GZipMiddleware` compressed each response as it was sent, about 2.8 ms of CPU for a 97 KB stylesheet, repeated for bytes that never change. `collectstatic` now writes a `.gz` beside every compressible file and the static handler serves it directly, with the original content type and `Vary: Accept-Encoding`. Measured on a single worker: 386 req/s before, 458 after. Images, fonts and files under 512 bytes are skipped.

- **`SERVE_STATIC`** — every other built-in can be removed: the admin by dropping its line from `urlpatterns`, sessions and authentication by dropping theirs from `MIDDLEWARE`. Static and media mounting had no switch at all — `STATIC_DIR = None` falls back to `./static`, which a scaffolded project has — so an API that serves no files mounted them anyway. `SERVE_STATIC = False` turns it off.

- **`TEMPLATE_OPTIONS`** — the Jinja environment was built by Starlette with no way to alter it, so `undefined`, `trim_blocks`, `lstrip_blocks` and the extension list were unreachable: a mistyped variable rendered as empty text rather than raising, and a project could not load `jinja2.ext.loopcontrols` or an extension of its own. Buraq builds the environment now, and anything Jinja's `Environment` accepts can be set here. `undefined` and `extensions` take dotted paths so a settings file never has to import jinja2, while options that are legitimately strings — `block_start_string` and the rest — are passed through untouched. `autoescape` keeps its default whatever else is set — without it every variable interpolated into a page is a cross-site scripting hole.

- **A new project is greeted rather than 404'd** — with nothing routed at `/`, a freshly scaffolded project answered `{"detail":"Not Found"}` at its own root, which reads as a broken install rather than an empty one. Buraq answers that one 404 with a page confirming the install works and pointing at the API docs and the admin. It is shown only while `DEBUG` is on, and it steps aside the moment the project routes `/` itself. The scaffold no longer writes a placeholder view into `config/urls.py`: a URL configuration is not where views belong, and a placeholder that has to be deleted is worse than a page that removes itself.

- **An app's own management commands can be run** — `BaseCommand` existed and its docstring described `myapp/management/commands/send_reminders.py`, but nothing ever looked in that directory, so a command written to the documented layout could be imported and never invoked. Each installed app's commands are now registered before the CLI parses its arguments: `buraq send_reminders --days 30` works, the command appears in `--help` with its `help` text, and its `add_arguments()` parser handles its own options. A command whose name is already Buraq's is refused with a message rather than replacing it.

- **`buraq.contrib.sessions` ships a migration** — the database session backend needed a `buraq_sessions` table, and the only instructions for creating it were a block of `CREATE TABLE` in the backend's docstring and the documentation for you to run by hand. It was the one table Buraq owned that Buraq would not create. The app now has a model and a migration like every other table-owning app: add it to `INSTALLED_APPS` and `buraq migrate` makes the table.

- **Token authentication** — the documentation described JWT settings, an `access_token` cookie and a bearer flow, none of which existed: there was no JWT code in the framework at all, and `pyjwt` had been dropped as a dependency nothing imported. `buraq.contrib.auth.tokens` now signs and verifies tokens with HMAC over `SECRET_KEY` — the same primitive the framework already signs with, so no dependency was added back. Signing in sets `access_token` beside the session cookie, and a request authenticates with either that cookie or `Authorization: Bearer`. `JWT_ALGORITHM` accepts the HMAC family and `JWT_EXPIRY_MINUTES` sets the lifetime.

  Verification is HMAC and nothing else, so a forged or expired token is rejected without a database query — 200 rejected tokens cost zero queries, which keeps an invalid token from being a way to make the database work. The algorithm inside a token is never trusted, only the configured one: a token claiming `"alg": "none"` is rejected rather than honoured, and signatures are compared in constant time. Logging out clears the cookie, which a session logout alone would not have done.

- **`DEFAULT_AUTO_FIELD`** — documented but unread, so the implicit `id` was always a 32-bit integer and a project that expected `BigAutoField` silently got a column that runs out near two billion rows. The setting is now honoured, and an unimportable path raises `ImproperlyConfigured` rather than being ignored.

- **`MIDDLEWARE`** — the middleware stack was hardcoded in `Buraq.__init__`, so none of it could be removed, reordered, or have anything inserted between its entries: a JSON-only API got cookie sessions whether it wanted them or not. The setting lists dotted paths outermost first, the same order the list reads in, and defaults to exactly the stack that was hardcoded. Buraq shipped seven middleware classes (`CommonMiddleware`, `ConditionalGetMiddleware`, `ContentSecurityPolicyMiddleware`, the cache pair, and more) that nothing could install, and six documentation pages already described a `MIDDLEWARE` setting that did not exist — both are now true.

- **`@register.global(takes_context=True)` / `@register.filter(takes_context=True)`** — the current render context (`request`, `SITE_FULL_URL`, and anything else a context processor added) can now be received as a global's or filter's first argument, wrapping `jinja2.pass_context`. There was previously no way for a templatetags.py helper to reach the request at all.

### Changed

- **The installation page leads with a project environment**, not
  `uv tool install`. A global tool install puts `buraq` on the PATH and holds
  Buraq and its own dependencies — and nothing of yours, so the first package
  your code imports is not there. That was hidden while `startproject` built a
  `.venv` and installed into it; now that it does not, the page has to say where
  packages go, and it does, with a section on adding your own.

  Three claims on that page had also stopped being true: that `startproject`
  installs dependencies, that a project contains an `alembic/` directory, and
  that `buraq` re-executes itself using `./.venv` so no activation is needed.
  Quickstart repeated the first of them and has been corrected too; the rest of
  that page was followed end to end against the current build and is accurate.

- **BREAKING — `startproject` no longer creates a virtualenv.** It writes the
  files and stops; `--install` asks for the old behaviour. Whoever ran the
  command already has an environment with Buraq installed in it, so building a
  second one inside the project was a guess about which environment they
  meant — not the container, not the conda environment, not the one they were
  standing in.

  Three faults came from that guess. `manage.py` carried eighteen lines to
  re-execute itself inside the project's `.venv`, which needed one branch to
  avoid orphaning the server on Windows and another to identify the environment
  on Linux and macOS, where the venv's python is a symlink to the system one and
  comparing resolved paths said they were the same interpreter. The install
  resolved Buraq from the index, so a project could not be run against a local
  build without reinstalling over the top. And a venv `uv` creates has no `pip`
  in it, so `python -m pip` inside a scaffolded project failed.

  `manage.py` is eleven lines now and re-executes nothing. `startproject` returns
  in about two seconds rather than after an install, and prints only what is
  left to do — `cd`, `migrate`, `runserver`. It briefly printed an environment
  step as well, which was advice to do what running the command had just proved
  was already done.

- **BREAKING — a default table name is pluralised as English, not by adding
  `s`.** `Category` produced `categorys`, and so did `boxs`, `classs`,
  `addresss` and `dishs` — names that then appear in every query, error message
  and database console for the life of the project. Words ending in `s`, `x`,
  `z`, `ch` or `sh` now take `es`, and a consonant before a `y` becomes `ies`.
  Irregular plurals are not attempted: `Person` is still `persons`, and
  `Meta.db_table` is the answer when the name matters.

  No table Buraq ships changes name, so the migrations it ships still apply. A
  project with a model whose name hits one of these endings has a table to
  rename; `buraq makemigrations` will not see it as a rename, so write that
  migration by hand or set `Meta.db_table` to the old name.
- **Generated migrations are numbered** — `0001_auto.py`, `0002_auto.py`, the
  same as the migrations Buraq ships, rather than Alembic's random hex. A
  directory listing now has the sequence in it. The revision id inside the file
  keeps the `<app>_<number>` form that keeps it unique across apps, since
  Alembic resolves by id and never by filename.

- **A scaffolded settings file names `USE_I18N` and `USE_TZ`** in the comment
  above the internationalization block. Both are on by default and the file
  writes only what a project is likely to edit, so neither appeared — with the
  result that the two settings someone arriving from another framework looks for
  first were absent, which reads as unsupported rather than as already on.

- **A scaffolded `config/settings.py` reads `DATABASE_URL` from the environment**
  — `DATABASE_URL = os.environ.get('DATABASE_URL', '...')`, the same shape as
  `SECRET_KEY` and `DEBUG` beside it. It was a bare literal, which was misleading
  rather than wrong: the scaffold also writes `DATABASE_URL` into `.env`, and the
  environment takes precedence, so editing the line in `settings.py` had no
  effect and nothing on the page said why. It also now points at the databases
  documentation, since a project has no other hint that `DATABASES` and read
  replicas exist.

- **`TEMPLATES_DIR` takes several paths, not one** — it was typed `str`, so a project with more than one template root — its own beside a shared theme — could name only one of them, and passing a list raised `TypeError: argument should be a str or an os.PathLike object`. It now accepts either, searched in the order given.

- **A scaffolded `config/urls.py` and `config/settings.py` explain themselves** — the two files a new project opens first said only "Add your apps here" and nothing at all. It now carries a header covering the three ways to add a route (function view, class-based view, another URLconf), the per-method helpers, that every path begins with a slash and a trailing one is ignored, and that which module is read comes from `ROOT_URLCONF`. `settings.py` now also shows `LANGUAGE_CODE`, `TIME_ZONE` and `AUTH_PASSWORD_VALIDATORS` — the first two because nearly every project changes them, the third because three validators were enforcing a password policy that appeared nowhere a reader would look. It gained a header covering the rule that only UPPERCASE names are read, that anything unnamed keeps its default, that values come from `.env`, and that a project's own settings work the same way.

- **BREAKING — `ROOT_URLCONF` is read, and a project's urls.py holds only urlpatterns** — the setting was declared and one management command read it; the application never did. So a project had to reach back for the application to load its own URLs (`app.load_urls(urlpatterns)` at the bottom of urls.py), which is why the application ended up being *built* there — `config/urls.py` created the app, declared the routes, registered them, and defined a view. The application now loads the module named by `ROOT_URLCONF`, so the scaffold splits into one job per file: `main.py` builds the application, `config/urls.py` is `urlpatterns`, `config/settings.py` names the urlconf. `app.load_urls()` still works for a project that would rather wire it by hand.

- **BREAKING — the admin is mounted from `urlpatterns`** — `BuraqAdmin(app)` was a call whose return value nothing read, made for its side effects, and it hid where the admin lived: the prefix was the string `"/admin"` inside the router, with no setting, argument or override, so the admin could not be moved off the first path a scanner tries. It is now `path("/admin", admin.site.urls)` — a line in `urlpatterns` like every other set of URLs, where the prefix is yours to choose and everything the admin builds follows it. `BuraqAdmin` is removed rather than kept alongside; two ways to mount the same thing is what made the prefix invisible in the first place.

  A second site can now be mounted at its own prefix — `path("/staff", private_site.urls)` — which the single hardcoded router could not express.

- **A model that declares its own primary key no longer gets an `id` beside it** — the implicit `id` was added whenever the model had no attribute called `id`, so a natural key — a session's key, a country's ISO code — ended up alongside a surrogate that meant nothing. It is now added only when the model declares no primary key of its own.

- **CORS is `buraq.middleware.cors.CORSMiddleware`** — the default stack named `fastapi.middleware.cors.CORSMiddleware`, the one entry that was not Buraq's own, and it leaked an implementation detail into every project's settings (FastAPI's class is Starlette's, re-exported). More than tidiness: Starlette's takes its configuration as constructor arguments, which a dotted path cannot supply, so the application kept a table mapping that one path to keyword arguments built from settings. Buraq's subclass reads `CORS_*` itself, and that table is gone — every entry in MIDDLEWARE is now constructed the same way, with no arguments.

  Leaving the old path in place would have failed silently rather than loudly: Starlette's class installs happily with no arguments and then applies no policy, so `CORS_ORIGINS` would be ignored and nothing would say so until a browser began refusing requests. A path Buraq no longer configures now raises `ImproperlyConfigured` naming its replacement — the same for `buraq.contrib.csrf.CsrfViewMiddleware` and `buraq.middleware.common.MessageMiddleware`, which moved.

- **BREAKING — CSRF protection is on by default** — sessions are cookie-based, so an unguarded POST is forgeable, and the check was opt-in. `CsrfViewMiddleware` is now in the default `MIDDLEWARE`. A client posting JSON must be issued the token first: make one safe request, read the `csrftoken` cookie, and send it back in `X-CSRFToken`. An endpoint authenticated some other way — a webhook signature, a bearer token — is decorated `@csrf_exempt`; removing the middleware from `MIDDLEWARE` turns the check off everywhere.

- **`CsrfViewMiddleware` moved to `buraq.middleware.csrf`, `MessageMiddleware` to `buraq.contrib.messages.middleware`** — core middleware belongs under `buraq.middleware`, an app's own middleware with the app; the two were the wrong way round, and `MessageMiddleware` sat in `common.py` beside three middlewares it has nothing to do with. The old paths are gone rather than aliased: two import paths for one class is the ambiguity that put them in the wrong place to begin with.

- **`APPEND_SLASH` now defaults to `False`** — Buraq registers every route without a trailing slash, so there was nothing for it to append one to.

- **A project has no `alembic.ini` and no `alembic/` directory** — both restated things the project already knew. The database came from settings and the version locations from `INSTALLED_APPS`, yet a second copy sat in a config file that went stale the moment an app was added; `env.py` was 59 lines without one reference to the project that owned it. The configuration is now built when a migration command runs, `script_location` resolves to `buraq.db:alembic` inside the installed package, and the locations are derived from `INSTALLED_APPS` — so adding an app to that list is the only step, with nothing to register. A leftover alembic.ini is ignored rather than read, so existing projects keep working and can delete it when convenient.

  Migration commands now call Alembic in process instead of spawning `python -m alembic` and reading its stdout. That parsing was matching on log wording (`Running upgrade`, `Detected`, a noise list), so a reworded Alembic message silently changed what the command printed; failures now arrive as `CommandError` rather than a returncode and a guess.

- **BREAKING — migrations live in the app that owns them** — a project kept one shared `alembic/versions/` for every model it had, so a migration's filename said nothing about which app it belonged to, deleting an app left orphans nobody could identify, and two people adding migrations on separate branches wrote into the same directory. Each app now keeps its own `<app>/migrations/`, next to the models the migrations describe, and `buraq startapp` creates the directory and adds the app to `version_locations` in alembic.ini. `makemigrations` visits each installed app in turn and writes at most one revision per app; `--app` narrows it to one. Without this nobody could publish a reusable Buraq app with models, since an installing project cannot invent the schema — which is exactly why the framework's own contrib apps already shipped per-app migrations.

  Autogenerate diffs against the database, so a revision written earlier in the same run leaves it behind and the apps after it cannot be read yet. The run stops there, reports what it wrote, and says to apply those and run again rather than failing outright.

- **The `versions/` directory level is gone** — Alembic's default layout puts migrations in a subdirectory because `script_location` also holds `env.py` and `script.py.mako`. An app directory holds neither, so the level separated nothing: framework migrations move from `buraq/contrib/<app>/migrations/versions/0001_initial.py` to `buraq/contrib/<app>/migrations/0001_initial.py`, and a project's are `blog/migrations/0001_initial.py` — the same shape the framework this borrows from uses.

### Removed

- **BREAKING — the uv wrapper commands.** `buraq install`, `buraq uninstall`,
  `buraq sync`, `buraq pip` and `buraq run` each did nothing but call the
  matching `uv` subcommand. They forwarded one option apiece — `--dev` and
  `--all-extras` — out of the sixty-odd `uv add` and `uv sync` accept, so
  anything beyond the simplest case had to be run against `uv` directly, and
  the names did not match what they wrapped (`install` for `add`). They also
  required uv unconditionally, which broke them in exactly the projects Buraq
  scaffolds without it, using the pip fallback.

  Use whatever the project already uses: `uv add`, `poetry add`, `pip install`.
  A web framework has no opinion worth adding here, and having one cost a
  supported surface that could only disappoint.

- **`CacheControlMiddleware`** — it set `Cache-Control` with `=` rather than
  `setdefault`, so adding it overwrote the static handler's header and put back
  the unconditional `immutable` described above. It was also a
  `BaseHTTPMiddleware`, which costs a task per request, and its path test could
  never match a `STATIC_URL` pointing at a CDN. The static handler sets these
  headers itself, correctly; remove the middleware from `MIDDLEWARE` if you
  listed it.

### Fixed

- **`send_many()` opened one SMTP connection per message.** It inherited a loop
  over `send()`, and `send()` uses aiosmtplib's one-shot helper — connect,
  negotiate TLS, authenticate, quit, for every message. Counted against a local
  server: five messages, five connections. The whole reason to batch is to pay
  that once, so the method was costing exactly what it existed to save. The SMTP
  backend now connects once, logs in once and sends the batch through it — five
  messages, one connection. A message the server rejects costs that message
  rather than the batch.

- **`from buraq.contrib.email import get_connection` raised ImportError.** The
  function lives in `buraq.contrib.email.send` and was never re-exported from
  the package, while the email page shows exactly that import. It is exported
  now, and a test asserts every name the page tells you to import is importable.
  The page also now shows `send_many()`, which is how several messages go over
  one backend — there is no connection object to open and close, so the batching
  is a method rather than a context manager.

- **A broken `admin.py` made a model vanish from the admin, silently.**
  `autodiscover()` wrapped the import in `suppress(ModuleNotFoundError)` to skip
  apps that have no `admin.py` — and that also swallowed a failed import
  *inside* one. A typo like `from .modelz import Post` meant the model simply
  never appeared, with nothing raised and nothing logged, which looks exactly
  like forgetting to register it. Whether the module exists is now asked before
  importing, so absence stays quiet and failure does not.

- **The tutorial's URL list could not reach half its own routes.** It put
  `path("/<str:slug>", ...)` before `path("/new", ...)`, and routes match top to
  bottom — so `/posts/new` matched the slug route with a slug of `"new"` and the
  create page was unreachable. Anyone following the tutorial got a broken app.
  Fixed segments now come before converters, with the rule stated, and the page
  says which parts introduce `PostForm` and the templates it names, both of
  which it used before the tutorial had written them.

- **`{{ csrf_input }}` rendered the function, not a field.** `csrf_input` and
  `csrf_token` are Jinja environment globals, and a global is a value rather
  than something a bare `{{ name }}` calls — so the form shown on every
  documentation page put `&lt;function _csrf_input at 0x…&gt;` into the HTML,
  and the POST that followed was refused with 403. Both are now supplied by
  `render()` as values that render themselves, so the documented form works.
  The token is only created when a template actually asks for one, and
  `csrf_input(request)` still works for anything written that way.
- **`buraq startapp` produced an app that could not run.** An app name is
  conventionally plural, and the scaffold appended `s` to it for every plural
  and capitalised it for the model — so `startapp posts` gave a `Posts` model
  whose table came out `posts_postses`, a view called `list_postss`, and
  templates under `postss/`. It named four templates and wrote none of them, so
  every page answered `TemplateNotFound`, and `admin.py` used an
  `@admin.register` decorator that does not exist, so the app never imported at
  all.

  The model is now the singular of the app name, the templates are written, the
  admin file uses `site.register()`, redirects go through `reverse()` rather
  than a hardcoded path that guesses where the project mounted the app, and
  `/new` and `/edit` are one route each with `methods=['GET', 'POST']` instead
  of two under two different names.

- **The ETag decorator hashed the response body twice on every request.** The
  digest was computed for the header and then computed again to compare against
  `If-None-Match` — the same bytes, the same answer, the first one discarded.
  About 2.2 ms per request on a 1 MB response, 0.3 ms on a 100 KB page. Hashed
  once and reused.
- **Buraq could not start on a FIPS-enabled system.** Six of its seven `md5`
  calls omitted `usedforsecurity=False`, and `hashlib` refuses to construct md5
  without it where FIPS is enforced. Every one of them is a cache key, an ETag
  or a file digest — never a security decision — so all now declare it.

- **`buraq check` passed on a project that could not start.** It reported "no
  issues" while `runserver` failed on the first line of `config/urls.py` — a
  package missing from the environment, a typo in an import, a view that had
  been renamed. Those are the likeliest ways a project breaks, and the one
  command meant to find problems before starting the server did not look at
  them. `urls.E001` now reports a URLconf that cannot be imported, naming what
  was missing, and `urls.E002` one that raises while importing.

- **A scaffolded `pyproject.toml` declared `buraq>=0.1.0`**, which accepts every
  release ever made — so a project generated today claimed compatibility with
  versions from before most of what it uses existed. The floor is now the
  version doing the scaffolding.
- **A scaffolded `pyproject.toml` configured uv**, with a `[tool.uv]` section
  saying uv managed the project's environment and lockfile. It does not: the
  project has no environment of its own, and whichever tool you use is your
  choice. The section is gone. `[dependency-groups]` stays — it is PEP 735, read
  by uv, pip 25.1+ and PDM alike, and the comment above it now says so rather
  than calling it a uv feature.

- **`python manage.py <command>` could not run an app's own commands.** It called
  `app()` while the `buraq` script calls `main()`, and only `main()` registers
  each installed app's commands before arguments are parsed — so the same
  command worked one way and answered "No such command" the other. `manage.py`
  now calls `main()` as well.
- **`manage.py` did not re-run itself inside the project's virtualenv on Linux
  or macOS.** It compared the resolved path of the running interpreter against
  the venv's, and on those platforms the venv's `python` is a symlink to the
  system one — so both resolve to the same binary, and running
  `python manage.py` with the system interpreter looked like it was already
  inside the environment. It is now `sys.prefix` against the venv directory,
  which is what actually distinguishes them. Windows was unaffected, since the
  venv holds a real copy there.

- **`STATICFILES_DIRS` was ignored while developing.** The development mount read
  only `STATIC_DIR`, while the finders behind `collectstatic` read
  `STATICFILES_DIRS` and each installed app's `static/` as well — so a project
  using the setting the framework itself prefers had its files collected
  correctly for production and answered with a 404 in development. That reads as
  a missing file rather than a missing mount, which is the wrong thing to go
  looking for. Development now serves every directory `collectstatic` collects
  from, in the same order, so what resolves in one resolves in the other —
  including each installed app's `static/`, which had the same problem: a file
  at `shop/static/shop/cart.js` is served at `/static/shop/cart.js`, so the
  directory to serve is the app's `static/` and not the one the file sits in.

  Development now resolves each request through the finders rather than mounting
  a list of directories, so it serves exactly what `collectstatic` collects —
  including from a custom finder, which mounting could not serve at all, since
  a finder offers files rather than directories.

- **Nothing said Buraq is single-database.** The migration guide called
  `DATABASE_URL` a replacement for the older framework's `DATABASES` dict, which
  reads as a change of syntax; it is a change of capability. There are no
  database routers and no read replica, and `QuerySet.using()` exists but raises
  `NotImplementedError`. The settings page and the migration guide now say so.
- **Three form widgets were in no documentation** — `PasswordInput`, and the
  `ChoiceWidget` and `FormatWidget` base classes. The widgets page now lists
  `PasswordInput` in its table, explains why it blanks the value on redisplay,
  and documents the two base classes with an example of subclassing each.

- **Static responses claimed `immutable` even when filenames were not hashed.**
  `immutable` tells a browser never to revalidate — not even on reload — and it
  was sent on every static response, including under the default storage, which
  does not hash. An edited stylesheet therefore did not reach anyone who had
  already loaded the old one until their cache entry expired a year later. The
  header now follows the storage: `max-age=31536000, immutable` when names are
  hashed, `max-age=60` when they are not. `STATIC_MAX_AGE` overrides the number
  and now defaults to `None`, meaning "choose by storage".

- **`STATIC_URL` without a leading slash crashed at startup.** `"static/"` reads
  like it means `/static/`, but it was passed through untouched: Starlette
  refused it as a mount path — `Routed paths must start with '/'` — and, where
  it did not crash, it rendered a *relative* href that resolved differently on
  every page. A leading slash is now added when missing. A trailing slash was
  never required, contrary to the comment in the docs, which said the opposite of
  the truth.

- **Hashed filenames did nothing on Windows.** Static names are URL paths, but
  they were built with `str(Path(...))`, which separates with a backslash there.
  The manifest was written keyed on `css\site.css`, every
  `{{ static('css/site.css') }}` lookup missed it, and the *unhashed* name was
  returned — so cache-busting was silently off, with nothing logged to notice.
  Had a lookup hit, the backslash went into the rendered href, which a CDN
  answers with a 404. Names are now POSIX everywhere they are produced or looked
  up.

- **Pointing `STATIC_URL` at a CDN crashed the application at startup.** The
  mount was attempted with the CDN host as its route path, and Starlette
  rejected it — `AssertionError: Routed paths must start with '/'`, naming
  neither the setting nor the CDN. The host is now dropped and the path kept, so
  a pull zone — which fetches from your origin on a cache miss — still finds the
  files where it expects them. Uploading to the CDN instead is `SERVE_STATIC =
  False`. The scheme-relative form (`//cdn.example.com/static/`) is recognised
  too, and a URL with no path left to mount (`https://cdn.example.com/`) mounts
  nothing rather than claiming `/`.
- **Static files and downloads returned an empty body on Granian.** Granian
  advertises the `http.response.pathsend` ASGI extension, so a file response
  hands the path to the server rather than writing a body. `GZipMiddleware`
  buffered only body messages and dropped the pathsend message, so the client
  received `200` with zero bytes. Every browser sends `Accept-Encoding: gzip`,
  so this affected every file served to every real client. The middleware now
  forwards pathsend untouched.
- `GZipMiddleware` no longer buffers responses it cannot compress. An
  incompressible or already-encoded response now streams through in its original
  chunks instead of being held in memory whole, so a large download no longer
  costs RAM proportional to its size.
- **The CSRF token repeated in every compressed response** — Buraq compresses by default, and a secret that appears unchanged in every response is the BREACH precondition: an attacker able to get reflected input onto a page reads the secret a character at a time from the response's compression ratio. The framework this borrows from ships compression *off* for exactly this reason and masks its token when you turn it on; Buraq shipped compression on and an unmasked token. The rendered token and the `csrftoken` cookie now carry the secret combined with a fresh random mask, so no two responses repeat it, and what is submitted is unmasked before comparison. Any token issued for the current session still validates.

- **`GZipMiddleware` compressed responses that were already compressed** — it never checked for an existing `Content-Encoding`, so a pre-encoded body came back as `content-encoding: gzip, gzip`: larger than the singly-encoded one, and the browser unpacks it twice.

- **Serving static files in production crashed** — the production path mounted WhiteNoise, which is WSGI: its `__call__(environ, start_response)` met an ASGI application's `(scope, receive, send)` and raised `TypeError: takes 3 positional arguments but 4 were given` on the first request for a file. Nobody hit it because whitenoise was not a dependency, so the `ImportError` fallback quietly served through `StaticFiles` instead — the broken branch was unreachable and untested.

  Production now serves through `StaticFiles` deliberately, with a `Cache-Control` header (`STATIC_MAX_AGE`, a year by default, `immutable` because collectstatic writes content-hashed names). Compression is not repeated: `GZipMiddleware` is in the default stack and already compresses these responses, which was WhiteNoise's main draw. Starlette's ETag and Last-Modified still give conditional requests a 304; the cache header is what saves the round trip entirely.

  For production at any size, Granian — already the default server — serves static files itself in Rust, with `SERVE_STATIC = False` and `--static-path-mount`. That is documented now, along with the fact that passing `--static-path-route` beside a single mount fails with a length mismatch.

- **The migration guide claimed a `TEMPLATES` setting** — its settings table mapped the older framework's `TEMPLATES` to a Buraq setting of the same name, which does not exist. The row now names the three that do: `TEMPLATES_DIR`, `APP_DIRS` and `TEMPLATE_OPTIONS`. The page also gained a section on why a new project's `INSTALLED_APPS` lists one app where the older framework's lists six.

- **`APP_DIRS` appeared in no documentation** — the setting that decides whether each installed app's `templates/` directory is searched was findable only by reading the source or running `diffsettings --all`. It is in the settings reference now, and the scaffolded `config/settings.py` header points at `buraq diffsettings --all` for the rest. The templates topic gained the `TEMPLATE_OPTIONS` section and the rule that a project's own directory is searched before an app's, so a file in `templates/` overrides one an app ships.

- **A command with a synchronous `handle()` failed after doing its work** — `execute()` passed the result of `handle()` to `asyncio.run()` unconditionally, so a command written with `def` rather than `async def` ran to completion and then raised `TypeError: a coroutine is required`. The result is only awaited when it is awaitable.

- **Admin templates could not be overridden** — the admin inserts its template directory into the Jinja environment rather than being discovered through `INSTALLED_APPS`, and it inserted it *first*. A project writing `templates/admin/login.html` to rebrand the admin was silently ignored, because the framework's copy was always found before it. The directory is appended now, so it is the fallback it was meant to be and a project template wins.

- **Six documented settings did nothing** — `SESSION_COOKIE_NAME`, `SESSION_COOKIE_MAX_AGE`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_HTTPONLY`, `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` appear in the settings documentation, but nothing read any of them: the session cookie and the connection pool used hardcoded values. All six are now declared and honoured.

- **Switching language never persisted** — `LocaleMiddleware` looks for the cookie named by `LANGUAGE_COOKIE_NAME`, and nothing ever set it: `set_language` redirected to the language-prefixed URL and left no trace, so cookie detection could not fire and `LANGUAGE_COOKIE_AGE` was unreachable. The view now sets the cookie.

- **Two settings for a feature that does not exist** — `ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` described JWT signing. There is no JWT code in the framework; `pyjwt` was dropped as a dependency nothing imported. Both removed.

- **Every static file request loaded the user from the database** — `AuthenticationMiddleware` runs before routing, so a logged-in visitor fetching a stylesheet did a user lookup for a response that cannot read `request.user`. In development, where Buraq serves static files itself, a page with twenty assets was twenty needless queries. Paths under `STATIC_URL`, `MEDIA_URL` and the admin's own mount now skip it.

- **CSRF could never validate a token** — the middleware generated one, put it in the `csrftoken` cookie, and stored it in `scope["_csrf_token"]`, which lasts one request. Nothing was written to the session, so the next request had nothing to compare against and every unsafe request was rejected, correct token or not. It also read `scope.get("session") or {}` — a new session is empty, which is falsy, so the fallback replaced the live session with a throwaway the token could not be written back through.

- **`@csrf_exempt` did nothing once the middleware was in the stack** — the decorator set `_csrf_exempt` on the view, and `CsrfViewMiddleware` never read it: it runs before routing, so it did not know which view a request would reach. It now resolves the route first, leaving a project a way to exempt the one endpoint that needs it. Without this there was no escape hatch, and the check could not have been made the default.

- **`CommonMiddleware` redirected forever** — with `APPEND_SLASH` on, it matched routes registered *without* a trailing slash, which is every route Buraq has, and redirected `/auth/register` to `/auth/register/`; Starlette's own `redirect_slashes` sent it straight back. Any project that added the middleware got `TooManyRedirects` on every request. It now redirects only when a route genuinely exists at the slashed path.

- **`request.user` raised on every request** — `AuthenticationMiddleware` reads the session and sets `request.user`, `@login_required` depends on it, and the middleware documentation listed it among the built-ins; nothing ever installed it. Touching `request.user` failed with Starlette's `AssertionError: AuthenticationMiddleware must be installed`. It is now in the default `MIDDLEWARE`, below `SessionMiddleware` because it reads the session, and an anonymous request gets `AnonymousUser` as documented.

- **The CORS setting was documented under a name that does not exist** — three pages showed `CORS_ALLOW_ORIGINS`; the setting is `CORS_ORIGINS`, so anyone copying the example configured nothing and got no CORS headers.

- **BREAKING — two apps could not both define a model of the same name** — a table was named after the model alone, so `Post` in `blog` and `Post` in `shop` both claimed `posts` and SQLAlchemy refused the second outright: `Table 'posts' is already defined for this MetaData instance`. The two apps could not be installed together at all. Table names now carry the app label — `blog_posts`, `shop_posts` — which is what makes a model name unique in the first place. `Meta.table_name` still overrides it, and the framework's own tables were already explicit, so only project models are affected: an existing project needs a migration renaming its tables, or a `Meta.table_name` pinning each one to the name it has.

- **A permission was unique across the whole database, not per model** — `codename` carried a global unique constraint, so `add_post` could exist only once. With two apps each defining a `Post`, the creation loop deduplicated on the codename and silently skipped the second, leaving one row shared between two models: granting it granted both, with no way to tell them apart. The constraint is now on (`content_type`, `codename`), which is the pair that is actually unique, and creation keys on the same pair. Migration `buraq_auth_0002` swaps it on existing databases.

- **BREAKING — `INSTALLED_APPS` no longer registers an app's URLs** — `Buraq.__init__` imported `<app>.urls` for every entry in `INSTALLED_APPS` and registered its `urlpatterns` under `getattr(urls_module, "prefix", "")`. Exactly one module in the framework declared a prefix, so every other app — including every app a project writes — was mounted at the site root, *in addition to* wherever the project's own `urlpatterns` put it. Following the scaffold's own instructions (`startapp posts`, add `'posts'` to `INSTALLED_APPS`, uncomment the `include`) bound each of its routes twice: once at `/posts/…` and once at `/`, where the list view shadowed the project's index view and `/<int:pk>` became a catch-all at the root. `buraq.contrib.auth` was the only app whose auto-registration landed anywhere sensible, and there it collided with the `include()` the scaffold writes — so every new project logged five `Duplicate Operation ID` warnings on startup.

  URLs now come from `urlpatterns` only, which is what the scaffold, every docstring and every documentation page already showed. `INSTALLED_APPS` keeps driving models, migrations, admin registration and `AppConfig.ready()`. A project relying on the old behaviour needs an explicit `path(..., include("<app>.urls"))` — the form it was already being shown.
- **The auth endpoint tables documented a route that does not exist** — `GET /auth/me` appears in two pages and in a `curl` example; `buraq.contrib.auth` has never served it. The tables now list what the app actually registers, which also restores the `GET /auth/login` and `GET`/`POST /auth/logout` routes they were missing.
- **Form widgets accepted no arguments** — `TextInput(attrs={"class": "form-input"})`, the constructor call shown in the widgets docs, raised `TypeError: TextInput() takes no arguments`; `Widget` had no `__init__` at all. Every built-in widget now takes `attrs=` and merges it with whatever a caller passes to `render()` (the widget's own attrs win on a conflicting key, matching `id`/`name` auto-fill from a bound field). `RadioSelect` and `CheckboxSelectMultiple` drop `id` from the per-option attrs so it is not duplicated across a group.
- **Fields defaulted to no widget at all** — `Field.__init__` set `self.widget = widget or {}`, a bare dict with no `render()`. Every field now gets a real widget instance by default (a new `widget_class` per field type — `NumberInput` for `IntegerField`/`FloatField`/`DecimalField`, `Select` for `ChoiceField`, `CheckboxInput` for `BooleanField`, and so on, matching the widgets doc's table), and passing a widget *class* rather than an instance (`CharField(widget=Textarea)`, also shown in the docs) is now instantiated automatically. `TextField`, `PasswordField` and `HiddenField` previously marked themselves with a string (`widget = "textarea"`) that got shadowed by `Field.__init__`'s own `self.widget = {}` and so was never actually read; they now carry real `Textarea`/new `PasswordInput`/`HiddenInput` widgets. `PasswordInput` never echoes a submitted value back into the rendered HTML unless `render_value=True`. `DateInput`/`DateTimeInput`/`TimeInput` also gained a `format=` constructor argument, alongside `attrs=`.
- **`{{ form.field }}` printed the raw value, not the widget** — `BoundField.__str__` returned `str(self.value or "")`, so a template that interpolates a field directly got plain text instead of an `<input>`. It now renders through the field's widget, like `.as_widget()`. The `as_p()`/`as_table()`/`as_div()`/`as_ul()` helpers had their own separate, narrower rendering path (a string comparison against `field.widget` that could never match a real widget instance, no `file` case at all, and no attrs of any kind); they now go through the same widget-rendering path.
- **`ModelForm.Meta.widgets` was accepted and silently ignored** — the auto-generated fields never looked at it. It now overrides the widget for any auto-generated field named in the dict, the same as an explicitly declared field's own `widget=`.
- **`i18n_patterns()`'s own docs example did not run** — `urlpatterns = [..., *i18n_patterns(...)]`, shown in the function's docstring and three places in the docs site, raises `TypeError: 'I18nURLGroup' object is not iterable`: `i18n_patterns()` returns a dataclass, not a list, and it has no `__iter__`. `register_urlpatterns()` already special-cased the group as a plain list *element* (`isinstance(item, I18nURLGroup)`), so that was always the only working form. Docs and docstring now show `i18n_patterns(...)` included directly, not spread.
- **A form's fields were shared across every instance of the form class** — `BaseForm.fields` returned a fresh `dict` on each access, but wrapping the *same* `Field`/`Widget` objects every time. A common pattern for locking a field on edit, `self.fields["slug"].widget.attrs["readonly"] = True` in `__init__`, therefore marked the field read-only for every subsequent instance of that form class, including unrelated requests, not just the one being edited. `fields` now deep-copies `declared_fields` once per instance.
- **BREAKING — `select_related()` and `prefetch_related()` never actually resolved a relation** — a `ForeignKey` field is a plain integer column; reading it returned the raw related id, with or without `select_related()`, and `.category.slug` raised `AttributeError` on the int. Both methods tried to apply a SQLAlchemy loader strategy (`joinedload`/`selectinload`) to that column or to the framework's own reverse-FK/many-to-many descriptors — none of which are real SQLAlchemy relationships — and raised `sqlalchemy.exc.ArgumentError: expected ORM mapped attribute for loader strategy argument` on every call. `Prefetch.apply()` existed and was documented (`post._prefetched_comments`) but `prefetch_related()` never called it, and it separately assumed a `<model>_id` column name this ORM does not generate.

  Fixed by batch-fetching instead of joining, after the main query runs: `select_related("category")` collects the raw ids and issues one follow-up query per named relation, then replaces the attribute on each instance with the resolved object — the *same* attribute name, so `doc.category` is the raw id normally and the `Category` instance once eager-loaded, never both at once and never a query on plain attribute access. `prefetch_related("docs")` / `prefetch_related(Prefetch("docs", queryset=...))` now does the equivalent for the reverse-FK and many-to-many direction, and the relation's own accessor picks it up: `category.docs.all()` and `post.tags.all()` return the cached list with no query once prefetched (previously always an unresolved `QuerySet`/coroutine, cached or not). Both are O(1) additional queries regardless of row count — no join, and no per-row queries either.

  Two more bugs surfaced by actually exercising this code path for the first time: `_ReverseFKDescriptor` resolved its child model with `getter() if callable(getter) else getter` — a class is itself callable, so this built a blank instance instead of using the class; and `QuerySet` had no `get()`/`get_or_none()` of its own (only `Manager` did), so any chain ending in one — `Post.objects.select_related("author").get(id=1)` — raised `AttributeError` regardless of relation loading. Both fixed; `Manager.get()`/`.get_or_none()` now delegate to `QuerySet`, matching `.exists()`/`.first()`/`.last()`.

## [1.6.0] - 2026-08-21

### Added

- **`buraq --version` and `python -m buraq`** — the conventional ways to check an install and to reach the CLI when its directory is not on `PATH`. Neither existed: `--version` fell through to a usage error and the package had no `__main__`.
- **`pip install "buraq[uv]"`** — an opt-in extra that brings uv along, so `buraq startproject` uses it instead of falling back to venv and pip. It is opt-in rather than a dependency because uv is a ~50 MB binary that nothing else in Buraq needs. uv is now also found beside the running interpreter, not only on PATH, which is what makes the extra work without activating the environment first.
- **`buraq startproject <name> <directory>`** — the target directory is now the second positional argument, the way `cp`, `mv` and `git clone` take theirs. It was `--dest` only, so the form most people try first failed with `Got unexpected extra argument`. `--dest` still works; passing both with different values is refused rather than silently preferring one.
- **Buraq ships migrations for its own tables** — the five contrib apps that own tables (`auth`, `contenttypes`, `flatpages`, `redirects`, `sites`) each carry an Alembic branch inside the package, applied only when the app is in `INSTALLED_APPS`. Previously every project autogenerated the framework's schema into its own history, so a release changing `buraq.contrib.auth` forced each project to generate and review a schema it does not own, and Buraq could not ship a data migration at all. Projects point at them with `version_locations`; nothing is copied in, so upgrading Buraq brings any schema change with it.
- **`buraq.apps.configure()`** — loads the settings module and imports every installed app's models from a synchronous entry point. `alembic/env.py` now calls it, so adding an app to `INSTALLED_APPS` is enough for migrations to see its models.
- **`DATABASE_ECHO` setting** — controls SQL statement logging explicitly. It was tied to `DEBUG`, so any project developing with `DEBUG = True` had every statement printed, including during management commands, which buried their own output. Now off by default; set `DATABASE_ECHO = True` to get it back.
- **`@app.on_startup` and `@app.on_shutdown`** — register coroutines to run around the framework's own startup and shutdown. Previously the only way in was to assign over `app._on_startup`, which replaced the framework's startup entirely: an app doing so lost system checks, template tag discovery, translation warmup and app loading, with nothing reporting it. Shutdown hooks run before the engine is disposed, so they can still use the database.
- **App configs are discovered from `<app>/apps.py`** — an `INSTALLED_APPS` entry naming a package (`"blog"`) now finds the `AppConfig` inside it instead of only accepting the full class path (`"blog.apps.BlogConfig"`). Where a module declares several, `default = True` picks between them; genuinely ambiguous cases fall back to a plain config rather than guessing. An `ImportError` raised *inside* an existing `apps.py` now propagates instead of being read as "no config here".
- **The CLI locates the project's settings module** — `buraq <command>` checks `config/settings.py`, `./settings.py`, then a single top-level package containing `settings.py`, so settings declared in Python rather than `.env` are actually loaded. `--settings` and `BURAQ_SETTINGS_MODULE` still take precedence, and scaffolded projects now set the latter in `manage.py`.
- **Model `Meta` options** — `Model._meta` now resolves 18 options, up from 7. New: `abstract`, `proxy`, `managed`, `db_table_comment`, `app_label` (with read-only `label` / `label_lower`), `get_latest_by`, `order_with_respect_to`, `default_related_name`, `base_manager_name`, `default_manager_name`, `permissions`, and `default_permissions`. `abstract` and `proxy` are deliberately not inherited, so a concrete child of an abstract model stays concrete even when it does `class Meta(Parent.Meta)`.
- **`Meta.abstract`** — a base model with no table of its own; its columns, including foreign keys, are copied into each concrete subclass, and reverse accessors are registered per subclass.
- **`Meta.proxy`** — reuse a parent's table with different Python behaviour (its own ordering, managers and verbose names). A proxy without a concrete parent raises `TypeError` at import.
- **`Meta.order_with_respect_to`** — adds an implicit `_order` column and generates `get_<model>_order()` / `set_<model>_order()` on the related model plus `get_next_in_order()` / `get_previous_in_order()` on instances. Combining it with `Meta.ordering` raises, since it sets the ordering itself.
- **Custom managers** — declare managers as class attributes and they are bound automatically; `Meta.default_manager_name` and `Meta.base_manager_name` select among them. Naming a manager that does not exist raises `ValueError` at import. `Manager()` no longer requires the model up front.
- **`Manager.exists()`, `.first()`, `.last()`** — these were documented but only existed on `QuerySet`, so `await Post.objects.exists()` raised `AttributeError`.
- **Automatic permission creation** — `buraq.contrib.auth` connects a `post_migrate` receiver that creates a `Permission` row for every model's `add`/`change`/`delete`/`view` set plus anything in `Meta.permissions`. Safe to re-run. Listing either `"buraq.contrib.auth"` or `"buraq.contrib.auth.apps.AuthConfig"` in `INSTALLED_APPS` enables it, or call `create_permissions()` yourself.
- **Query expressions on `buraq.models`** — `Q`, `F`, `Case`, `When`, `Value`, `OuterRef`, `Subquery`, `Exists`, `ExpressionWrapper`, the aggregates and the window functions are re-exported, so `from buraq import models` covers models, fields and queries in one import. The specific modules still work and return the same objects.
- **Per-concern decorator modules** — `buraq.contrib.auth.decorators`, `buraq.views.decorators.http`, `.cache`, `.csrf`, `.vary` and `.csp`, alongside the flat `buraq.decorators` namespace. `buraq.views.decorators.csp` was documented but did not exist; `buraq.views.decorators` was a plain module, so the submodule import raised `ModuleNotFoundError`.
- **Documentation: Sync and Async Code** — when a synchronous view is acceptable (and why it cannot reach the ORM), how to call blocking libraries with `asyncio.to_thread()`, and why no sync bridge ships.

### Changed

- **BREAKING — `render()` is now a coroutine** — `buraq.shortcuts.render()` must be awaited: `return await render(request, "posts/list.html", {"posts": posts})`. It was synchronous while `run_context_processors()` was a coroutine, so the coroutine was never awaited and context processors silently did nothing (see Fixed). Making `render()` async also allows a context processor to query the database, which was previously impossible — every query in the ORM is `await`-only, so a synchronous processor could only read attributes already on the request. All bundled views, the `startapp` scaffold, and every documentation example are updated.
- **Permission creation issued one INSERT per permission** — plus a SELECT after each. It is now a single bulk insert: 189 ms to 39 ms for 36 permissions, and the gap widens with model count.
- **Command output has one vocabulary** — every command printed through bare `typer.echo`, so an error read the same as a note, and Alembic's three setup lines appeared on every migration ahead of whatever the command had actually done. Status messages now carry a consistent mark and colour, Alembic's chatter is filtered while its progress is kept, and the commands that emit pipeable data — `dumpdata`, `sqlflush`, `inspectdb` and the rest — are deliberately left unstyled. Symbols fall back to ASCII where the terminal cannot encode them.
- **`runserver` says what it started, once** — the address was printed three times over, by the banner and then by the server's own startup lines, alongside worker PIDs. Both servers now share one three-line banner and run at `warning` rather than `debug`; startup failures still surface.
- **`buraq startproject` installs the project's dependencies** — it wrote the files and left the reader to run `uv sync`, or a three-line venv-and-pip incantation, before anything could run. There was no decision in that step: a project cannot start without its dependencies. It now installs them, using uv when present and a `.venv` with pip otherwise. `--no-install` writes the files alone, and an install that cannot finish leaves the project intact and reports the one step outstanding rather than failing the command.
- **`buraq migrate` applies every branch** — the default target is `heads` rather than `head`, which fails outright once more than one branch exists. `makemigrations` pins new revisions to the project's own directory and branch; with several version locations Alembic picks one itself, and it chose the installed package.
- **Scaffolded `alembic.ini` sets `path_separator = newline`** — Alembic's default of `os` means `;` on Windows and `:` elsewhere, so a committed config would not parse on the other platform. One path per line is portable and survives directory names containing spaces.
- **`makemigrations` says what its argument is** — the positional argument is the migration's description, which reads as an app label to anyone arriving from a framework whose equivalent scopes the run to one app. Buraq keeps a single migration history for the whole project, so `buraq makemigrations posts` would quietly create a migration *described* "posts" containing every pending change. The command now says so when the text matches an installed app, and the help text and reference spell it out.

### Removed

- **Three dependencies nothing imported** — `pyjwt[crypto]`, `secure` and `aiofiles`. There is no JWT anywhere in Buraq: the only tokens are the ones the password-reset flow generates, and security headers are set by hand from the `SECURE_*` settings. Dropping `pyjwt` takes `cryptography` with it, about 10 MB off every install.
- **`node_modules` from version control** — 456 files, including platform-specific shims, were committed and no ignore rule covered them. Adding the rule alone does nothing for tracked paths, so they are removed from the index.
- **MkDocs configuration and source** — the documentation site is Astro + Starlight; `mkdocs.yml`, the old `docs/` tree and the `mkdocs`/`mike` dependency group are gone. The site now lives at `docs/`, and the admin panel stylesheet build moved from `frontend/` to `assets/`.
### Fixed

- **The JSON cache backends silently changed values** — `FileCacheBackend` and `RedisCacheBackend` serialized with `json.dumps(value, default=str)`, so a value JSON cannot hold was stored as its repr: a `datetime` went in and a `str` came back, with the mismatch surfacing wherever the value was next used rather than at the call that cached it. They now raise `TypeError` naming the value and the key.
- **`buraq check` discarded its hints** — every check carries a hint explaining what to do about it, and the command printed only the message.
- **`clearsessions` reported a missing table as a stack trace** — including the SQL and its parameters. A project using cookie sessions has no such table, which is ordinary rather than exceptional.
- **A new project rejected its own URL** — `runserver` binds 127.0.0.1 and every banner and guide points there, but the scaffolded `ALLOWED_HOSTS` listed only `localhost`, so the first page a developer opened answered `400 Invalid host header`. Both spellings of the loopback address are now allowed, and `ALLOWED_HOSTS` accepts a comma-separated string as well as JSON so a `.env` entry and a settings module cannot disagree about its format.
- **A scaffolded `.env` did nothing** — `config/settings.py` read `os.environ`, which never sees `.env` on its own, so `DEBUG=True` in the file left the project running with `DEBUG=False`. Among other things that turned off the API docs the startup banner advertises. The generated settings module now loads `.env` before reading it.
- **`buraq shell -c` could not run an await** — every ORM call is awaitable, so a useful one-liner nearly always contains `await`, and the command rejected them with `SyntaxError: 'await' outside function`. Top-level await now compiles and runs.
- **`buraq startapp` created an unused `migrations/` directory** — migrations live in `alembic/versions/`, so an app-level directory only invited people to put files where nothing would read them.
- **`buraq startproject` exited 1 after successfully creating a project** — it finished by asking whether to run `uv sync`, and reading that confirmation from a closed stdin aborted the command. The project was on disk, but the exit code said failure, so `buraq startproject x && cd x` broke in scripts and CI. The prompt is gone: it duplicated the step the command already prints, and scaffolding should not depend on someone being there to answer.
- **Getting-started guides assumed uv was already installed** — every command used `uv`, with no note that it is a separate install or that pip works throughout. The requirements section now checks Python, explains the choice, links uv's installer, and gives a pip path for each step. `buraq startproject` likewise printed `uv sync` as the next step even on a machine without uv; it now prints the venv and pip commands there instead.
- **The documented first-run migration sequence was wrong** — the quickstart ran `buraq migrate` straight after defining a model, which applies only the migrations Buraq ships and leaves the model's table missing. Autogeneration also refuses to run while the database is behind, so a new project needs `migrate`, then `makemigrations`, then `migrate`. Both the quickstart and the migrations reference now say so.
- **The installation guide's first command could not work** — it opened with `uv add buraq`, which requires a `pyproject.toml` that a new user does not have yet and fails with `No pyproject.toml found in current directory or any parent directory`. The database-driver and extras sections had the same problem, telling you to add dependencies before a project existed. The page now installs the command with `uv tool install buraq`, creates the project, and only then adds drivers from inside it.
- **`buraq startproject` failed on a machine with no project** — an insecure `SECRET_KEY` was enforced while `buraq.conf.defaults` was being imported, so `import buraq` raised whenever `DEBUG` was off and no key was set. That is the situation the very first command a user runs is in. Enforcement now rests on the system checks that already covered it (`security.E001`), which run at application startup and still refuse to serve with a placeholder key; the placeholder itself is a single constant shared by the field default and the check rather than three copies of one literal.
- **Template snippets rendered without highlighting** — 37 code blocks were fenced `html+jinja` or `html+django`, names carried over from the previous documentation tooling. Shiki has no grammar under either, so every build logged a warning and fell back to plain text. Both now alias to the bundled `twig` grammar, which highlights HTML with `{% %}` and `{{ }}` tags.
- **A newly created project could not generate its first migration** — the scaffolded `alembic/env.py` imported no models, so `Base.metadata` was empty in the Alembic process and autogenerate reported no changes. `startproject` → `makemigrations` → `migrate` produced a database containing only `alembic_version`, and the documentation compounded it by stating that `migrate` alone creates the tables.
- **Twenty-three settings could not be set** — `CACHE_TABLE`, `ROOT_URLCONF`, `APPEND_SLASH`, `SESSION_ENGINE`, `CONTENT_SECURITY_POLICY`, `ADMINS`, `TASKS` and others were read through `getattr(settings, ...)` but never declared, so assigning one raised `ValueError` and a settings module naming one was ignored. Most were already documented. All are now declared with their previous fallbacks as defaults.
- **Autogeneration proposed dropping the cache and session tables** — the database cache and session backends create their tables with raw SQL, so they are absent from `Base.metadata` and Alembic treated them as tables to remove. Both are now excluded alongside `Meta.managed = False` models.
- **`inspectdb` crashed with `MissingGreenlet`** — the reflection Inspector was created inside `run_sync()` but used outside it, so the first `get_columns()` attempted IO with no greenlet. It also generated `IntegerField(, null=False)` — invalid Python — for any non-nullable column whose field type takes no arguments.
- **`dumpdata` emitted `{}` and `sqlflush` emitted nothing** — both read `Base.metadata`, which is empty until something imports the models. Nine commands that read the model registry now load the installed apps first.
- **`remove-stale-contenttypes` always failed** — it imported `ContentType` from `buraq.contrib.contenttypes` rather than `.models`, which raised `ImportError` on every run; the guard meant to catch that could not, since a class is always truthy. A missing content types table is now reported as a setup step rather than a traceback.
- **Scaffolded projects logged the format string instead of the message** — `alembic.ini` escaped `%` as `%%`, so every Alembic log line read `%(levelname)-5.5s [%(name)s] %(message)s`.
- **`migrate` on a fresh project printed a traceback** — permission creation ran before the auth tables existed. A database without them is a normal state for a new project and is now skipped quietly.

- **Scaffolded projects did not start when created on Windows** — `startproject` wrote its files with the locale encoding, so a template containing an em dash landed as cp1252 while Python reads source as UTF-8. The generated `main.py` failed with `SyntaxError: Non-UTF-8 code starting with ''` before the project ever ran. Every file Buraq reads or writes now names UTF-8 explicitly.
- **Session and cache file backends depended on the machine's locale** — entries were written and read with the platform default encoding, so anything non-ASCII was corrupted between environments and raised `UnicodeEncodeError` outright under the POSIX locale that minimal container images use. Both now use UTF-8.
- **CI only ran on Linux** — the platform-specific paths (scaffolding, the virtualenv re-execution, shelling out to alembic) were never exercised on the systems where they differ, which is how the Windows scaffolding fault shipped. The suite now runs on Linux, Windows and macOS.
- **Migration output was unreadable** — `migrate` printed the SQL behind permission creation, and `makemigrations` printed a line per Alembic autogenerate plugin, so the one line that mattered scrolled away. Statement logging is now opt-in via `DATABASE_ECHO`, and scaffolded projects quiet `alembic.runtime.plugins`.
- **Migration signals sent kwargs the documentation did not match** — receivers were promised `app_config`, `verbosity`, `interactive` and `using`, but only `revision` was ever sent. `verbosity` is now sent as well and the reference lists what actually arrives.
- **`AppConfig.ready()` never ran, anywhere** — nothing in the framework called `apps.populate()` or `apps.run_ready_hooks()`, so the app registry was always empty and every app's `ready()` was dead code. Since `ready()` is where an app connects its signal receivers, anything depending on one silently did nothing. Both the ASGI lifespan and the CLI now load app configs through a single shared entry point.
- **`pre_migrate` and `post_migrate` never fired** — the CLI called `Signal.send()`, a coroutine, without awaiting it; the resulting `RuntimeWarning: coroutine 'Signal.send' was never awaited` was the only sign, and the surrounding `except Exception: pass` would have hidden anything else. The CLI now runs receivers to completion on one event loop and logs a failing receiver instead of discarding it, without failing a migration that already applied.
- **Automatic permission creation never created anything** — a consequence of the two faults above: `migrate` completed and left `buraq_permissions` empty. Permissions are now created for every installed app's models.
- **Management commands did not import app models** — commands that walk the ORM registry saw only the models something else happened to import first, so permission creation covered the bundled auth models and none of the project's own. Every installed app's `models` module is now imported during setup.
- **`makemigrations` wrote an empty migration when nothing had changed** — autogenerate always emits a revision file, so an unchanged project accumulated revisions whose `upgrade()` was `pass`, indistinguishable in the history from real ones. Empty revisions are now discarded with `No changes detected`; unreadable files are never deleted.
- **`makemigrations` reported a stale database opaquely** — Alembic's `Target database is not up to date` does not say what to do about it. The command now adds that `buraq migrate` needs running first.
- **Scaffolded `manage.py` detached itself on Windows** — it re-executed through `os.execv()`, which on Windows spawns a child and exits the parent, so the shell returned its prompt while the server kept running unreachable by Ctrl+C. It now runs the child and propagates its exit code, matching the `buraq` console script.
- **`Meta.ordering` never reached a query** — the value was stored on the model but never applied, so a model declaring `ordering = ["-created_at"]` returned rows in unspecified order. Ordering is now applied to every queryset; an explicit `order_by()` replaces it rather than appending to it, and `order_by()` with no arguments clears it.
- **Reverse foreign-key accessors were never created** — `Author.book_set` did not exist for any model. The pass that registers them looked for `Field` objects, but an earlier step had already replaced those with SQLAlchemy `Column`s, so the check never matched. Foreign keys are now captured before that conversion, which also makes accessors work for keys inherited from an abstract base.
- **`TEMPLATE_CONTEXT_PROCESSORS` silently did nothing** — `render()` called the asynchronous `run_context_processors()` from synchronous code, producing a coroutine; the resulting `TypeError` was swallowed by a bare `except`, leaving every template without `request`, `user` or `LANGUAGE_CODE`. Processor failures are now logged instead of discarded.
- **`Meta.managed = False` was ignored by migrations** — unmanaged tables were excluded from `create_tables()` but migration autogeneration still emitted `create_table` for them. An `include_object` filter is applied, and `startproject` scaffolds it into new projects.
- **Unknown `Meta` attributes were ignored** — a typo such as `orderring` left the model on default behaviour with no indication. `class Meta` now raises `TypeError` naming the invalid attributes.
- **Test suite could not run from a clean clone** — the settings layer refuses to import without a real `SECRET_KEY` and `.env` is gitignored, so the documented `pytest` command failed until a developer hand-wrote one. `tests/conftest.py` now sets a test-only environment, keeping the suite hermetic.
- **Release workflow pointed at a removed directory** — the docs deployment steps still referenced the previous documentation tooling (`website/`, `versioned_docs/`, `npm run docs:version`); none of those paths exist, so the next release would have failed while installing dependencies. The workflow now builds `docs/` and publishes `docs/dist`, adding `.nojekyll` so Pages does not drop the `_astro/` asset directory.

### Security

- **The database cache interpolated its table name into SQL** — a table name cannot be a bound parameter, so `CACHE_TABLE` is now rejected unless it is a plain identifier. The value comes from settings rather than a request, which makes this a guard rather than a fix, but a setting read from an environment variable is one indirection from somewhere less trusted.
- **Documented what each cache backend serializes with** — `DatabaseCache` and `MemcachedCacheBackend` read values back with `pickle.loads`, which runs code by design, so anyone able to write to that table or Memcached instance can run code in the application. It is the conventional trade-off for a pickle-backed cache, and it is safe only while the store is as trusted as the application; that condition was nowhere in the documentation.


## [1.5.2] - 2026-08-12

### Fixed

- **`contrib/auth/urls.py` — `AttributeError` at startup** — URL patterns still referenced `views.obtain_auth_token` and `views.get_me` which were removed in 1.5.0; any app with `buraq.contrib.auth` in `INSTALLED_APPS` crashed at startup with `AttributeError`; replaced with `LoginView.as_view()` and `LogoutView.as_view()`
- **CBV routes without path parameters returned 422** — `_patch_cbv_signature()` in `buraq/urls.py` returned early when a route had no path parameters, leaving `**kwargs` visible in the function signature; FastAPI treated `kwargs` as a required body field and rejected all requests with 422; the patch now always runs for CBV views
- **`registration/login.html` missing from package** — `LoginView` renders this template on failed authentication but it was never shipped; users got `TemplateNotFound` on any wrong-password login attempt; the template is now included in `buraq/contrib/auth/templates/`

## [1.5.1] - 2026-08-12

### Fixed

- **`buraq.contrib.staticfiles` missing from PyPI wheel** — the entire `contrib/staticfiles/` package was excluded by an overly broad `.gitignore` entry (`staticfiles/` matched the source directory); the pattern is now anchored to the repo root (`/staticfiles/`) so the module ships correctly
- **`buraq.contrib.auth.validate_password` raised `ImportError`** — the shortcut re-export was dropped from `buraq.contrib.auth.__init__`; `from buraq.contrib.auth import validate_password` now works as documented
- **`contrib/auth/views.py` — `NameError: check_password`** — `check_password` was called in the password-change view but not imported; raises `NameError` at runtime for any user who triggers that view
- **`test/testcase.py` — `assertNumQueries` always reported 0** — `_QueryCounter.start()` computed the engine reference and discarded it; `stop()` was a no-op; the counter now registers a SQLAlchemy `before_cursor_execute` event listener, matching the implementation used by `_AssertNumQueriesContext`
- **`management/cli.py` — `listurls` name column not padded** — the name-column width was computed by `max()` but the result was never stored; long route names extended past the separator line; the width is now applied to the `name` column in `_fmt`
- **`contrib/cache/backends/base.py` — `zip(strict=False)` was a no-op** — `strict=False` is the default; changed to `strict=True` so a length mismatch between keys and gathered results raises immediately instead of silently truncating the returned dict

## [1.5.0] - 2026-08-12

### Security

- **Path traversal in `FileSystemStorage`** — `_full_path()` used `os.path.normpath` + `lstrip` which did not resolve symlinks; a name like `../etc/passwd` bypassed the check. Now uses `os.path.realpath()` to resolve all `..` components and symlinks, then verifies the result starts with the storage root. `SuspiciousFileOperation` is raised before any disk I/O occurs.
- **Open redirect in `RedirectFallbackMiddleware`** — `new_path` values were used as-is without validating they were relative paths. An attacker with database write access could store `https://evil.com` and turn the middleware into an open redirector. The middleware now rejects any `new_path` with a scheme or netloc; the original 404 is forwarded instead.
- **CSRF `Secure` cookie flag** — `ensure_csrf_cookie` did not set the `Secure` flag, allowing the CSRF token to be transmitted over plain HTTP in production. The flag is now set automatically when `DEBUG=False`.
- **Default `SECRET_KEY` in production** — using the placeholder key outside `DEBUG` mode now raises `ImproperlyConfigured` at startup rather than silently running with an insecure key. A warning is printed in `DEBUG` mode.
- **`startproject` key generation** — generated `config/settings.py` previously hard-coded the insecure placeholder key. `startproject` now generates `SECRET_KEY = secrets.token_hex(50)`, writes a placeholder to `.env.example`, and scaffolds `settings.py` to read the key from `os.environ`.
- **SSL redirect host-header injection** — `SecurityMiddleware` with `SECURE_SSL_REDIRECT=True` validated the scheme but not the `Host` header. An attacker could inject a crafted `Host` to redirect victims to an unexpected domain. The redirect is now rejected with `400 Bad Request` if `Host` is not in `ALLOWED_HOSTS`.
- **`register()` race condition** — the user-registration endpoint used a check-then-create pattern with a TOCTOU gap: two concurrent requests could both pass the "does username exist?" check and both attempt an insert. Now uses try-create-catch-`IntegrityError`.
- **CORS wildcard fallback** — `CORSMiddleware` fell back to `["*"]` when `CORS_ORIGINS` was empty or unset, enabling cross-origin requests from any domain by default. The middleware now sends no `Access-Control-Allow-Origin` header when `CORS_ORIGINS` is empty.
- **SMTP error disclosure** — `SMTPEmailBackend` printed the full exception traceback to stdout on failure. In production this could leak SMTP credentials through log aggregation. All exceptions are now logged via `logging.exception()` at `ERROR` level.
- **Event-loop blocking on password hashing** — `make_password()` and `check_password()` called Argon2 synchronously, blocking the event loop for ~100 ms on every hash/verify. Both are now `async` and run via `asyncio.to_thread()`. `ModelBackend.authenticate()` received the same fix.
- **Username enumeration via timing** — `ModelBackend` returned instantly when a username did not exist but waited ~100 ms for Argon2 when the password was wrong, allowing timing-based username enumeration. A dummy Argon2 verify is now run for missing users so all code paths take the same time.
- **Session cookie served from page cache** — `@cache_page` stored the full response header dict, including `Set-Cookie`. A cached response was then served to other users with the original user's session cookie embedded. `set-cookie`, `authorization`, and `www-authenticate` headers are now stripped before storing.
- **Broken redirect URL on login** — `@login_required` embedded the raw current URL as the `next` query parameter without encoding it. A URL containing `?`, `&`, or `=` would corrupt the redirect query string. The value is now encoded with `urllib.parse.urlencode`.
- **SHA-1 as default in `salted_hmac`** — SHA-1 has been cryptographically broken since 2005. The default `algorithm` argument was `"sha1"`; it is now `"sha256"`.
- **Unbounded language code in `set_language` view** — a caller could POST an arbitrarily long `language` parameter. The view now rejects language codes longer than 500 characters.

### Added

**Built-in Admin Panel**
- `buraq.contrib.admin.BuraqAdmin` — mounts the admin panel onto a `Buraq` app; auto-discovers every installed app's `admin.py` on startup; no third-party dependencies
- `buraq.contrib.admin.ModelAdmin` — per-model configuration class; options: `list_display`, `search_fields`, `ordering`, `list_per_page`, `fields`, `readonly_fields`, `can_create`, `can_edit`, `can_delete`
- `buraq.contrib.admin.AdminSite` — central model registry; `register()`, `unregister()`, `is_registered()`, `autodiscover()`; module-level `site` singleton; supports isolated multi-tenant sites via `BuraqAdmin(app, admin_site=private_site)`
- Auto-CRUD views at `/admin/{app}/{model}/` — list with search and pagination, add form, change form, delete confirmation
- List view renders boolean columns as coloured badges; type-aware form fields (checkbox, textarea, datetime-local, number)
- Admin cookie auth (`_buraq_admin` cookie, HMAC-SHA256 signed with `SECRET_KEY`); any `is_staff` or `is_superuser` account can log in
- Darkberry-themed UI using Frutjam CSS + Tailwind CDN; sidebar groups models by app label

**Debug Error Page**
- `buraq.core.debug.render_debug_page(request, exc)` — full-page HTML traceback shown in the browser when `DEBUG=True`; project frames highlighted, library frames dimmed
- Displays: exception type + message, each frame with source context (5 lines), collapsible local variables, chained-exception notice, query params, and request headers (cookie header excluded)
- Plain-text traceback section for copy-paste
- Registered automatically in `Buraq._register_exception_handlers()`; zero configuration required

**Management Commands**
- `--settings MODULE` global option — accepted by every `buraq` command; loads the named settings module before the command runs, overriding the defaults (e.g. `buraq migrate --settings config.prod_settings`); also read from the `BURAQ_SETTINGS_MODULE` environment variable
- `createsuperuser` — completely rewritten: interactive prompts for username, email, and password with two-pass confirmation; checks for duplicate username and email before inserting; accepts `--username`, `--email`, `--password`, and `--no-input` for scripted/CI use; uses `User.objects.create()` instead of raw SQLAlchemy session

**Static Files — complete feature set**
- `STATICFILES_DIRS` setting — list of source directories searched by finders (replaces single `STATIC_DIR`; `STATIC_DIR` kept for backward compatibility)
- `STATICFILES_FINDERS` setting — list of finder class paths; defaults to `FileSystemFinder` + `AppDirectoriesFinder`
- `STATICFILES_STORAGE` setting — pluggable storage backend class path; defaults to `StaticFilesStorage`
- `buraq.contrib.staticfiles.finders.FileSystemFinder` — searches all `STATICFILES_DIRS` in order; first match wins
- `buraq.contrib.staticfiles.finders.AppDirectoriesFinder` — searches each installed app's `static/` subdirectory
- `buraq.contrib.staticfiles.finders.find(path)` — module-level helper; returns absolute path or `None`
- `buraq.contrib.staticfiles.finders.get_files()` — yields `(relative, absolute)` pairs across all finders, deduplicated
- `buraq.contrib.staticfiles.storage.StaticFilesStorage` — default local filesystem backend; `url()`, `path()`, `exists()`, `save()`, `post_process()`
- `buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage` — post-processes collected files to append content-hash to filenames (e.g. `style.abc123de.css`); writes `staticfiles.json` manifest; `url()` returns hashed URL automatically
- `buraq.contrib.staticfiles.storage.get_storage()` — lazy singleton accessor for the configured storage backend
- `buraq.contrib.staticfiles.storage.reset_storage()` — clears cached storage instance for use in tests with `override_settings`
- `buraq.contrib.staticfiles.templatetags.StaticExtension` — Jinja2 extension registered automatically; adds `{% static 'path' %}` and `{% media 'path' %}` block tags with no `{% load %}` required
- `{{ media('path') }}` template global — resolves media file URLs via `MEDIA_URL`; symmetric with `{{ static('path') }}`
- `{{ static('path') }}` now routes through the configured storage backend — returns hashed URLs automatically when `ManifestStaticFilesStorage` is active
- `buraq collectstatic` — updated to use finders (discovers from all configured dirs and apps) and storage (calls `post_process()` for manifest generation); output now shows `Post-processed` count

**Bug Fixes**
- `db/transaction.py` — replaced `_Atomic` singleton (shared instance state caused session corruption under concurrent requests) with a plain `atomic()` function; `async with atomic():` returns a fresh `_atomic_cm()` each call; session leak on commit failure also resolved
- `orm/manager.py` — `RelatedManager.get()` now raises `DoesNotExist` / `MultipleObjectsReturned` instead of returning a list
- `orm/manager.py` — `RelatedManager.add()` / `remove()` now issue one bulk `UPDATE … WHERE id IN (…)` instead of N individual `save()` calls
- `serializers/base.py` — `_load_records()` now batches existence checks per model class (one `SELECT … WHERE id IN (…)`) instead of one query per record
- `signals.py` — `send_sync()` now logs handler exceptions via `logging.getLogger("buraq.signals").exception()` instead of silently swallowing them
- `test/testcase.py` — `TransactionTestCase._begin_transaction()` now sets `_current_session` to the test connection so ORM calls inside the test use the same session; `_rollback_transaction()` fixed to call `rollback()` explicitly and close cleanly
- `test/testcase.py` — `LiveServerTestCase` replaced `asyncio.ensure_future(..., loop=self._loop)` (removed in Python 3.10) with `self._loop.create_task()`
- `test/testcase.py` — `override_settings` replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.get_running_loop().create_task()` (async context) / `asyncio.run()` (sync context); signal is no longer silently dropped inside async tests
- `contrib/email/backends/locmem.py` — logs a warning when `outbox` exceeds 500 messages to prevent silent unbounded memory growth in long-running test suites
- `contrib/staticfiles/handlers.py` — `StaticFilesHandler` now mounts media files via `_mount_media()`; WhiteNoise fallback now logs a warning instead of silently degrading; wired into `application.py` replacing `register_static()`

**Cache — Multi-backend and middleware**
- `CACHES` dict setting — configure multiple named backends identical to the standard multi-cache pattern; `caches["alias"]` proxy object routes to any named backend
- `buraq.contrib.cache.core.caches` — `_CachesHandler` dict-style proxy; `caches["default"]` returns the default backend, `caches["sessions"]` returns any named backend from `CACHES`
- `DatabaseCache` backend (`buraq.contrib.cache.backends.db`) — SQL table-backed cache; create table via `python manage.py createcachetable`
- `CacheMiddleware` (`buraq.middleware.cache`) — full per-view response cache; caches all `GET`/`HEAD` responses; skips `no-store`/`private`/`no-cache`
- `FetchFromCacheMiddleware` — outer half of the layered cache pair; returns cached response before the view runs
- `UpdateCacheMiddleware` — inner half; stores the view response in cache after it runs

**Sessions — Server-side backends**
- `buraq.contrib.sessions.backends.base.SessionBase` — abstract base class for all server-side session backends; uniform async API: `get`, `set`, `pop`, `clear`, `flush`, `cycle_key`, `save`, `load`, `delete`, `exists`
- `buraq.contrib.sessions.backends.file.FileSessionBackend` — JSON files under `SESSION_FILE_PATH`; expired files cleaned on access
- `buraq.contrib.sessions.backends.db.DatabaseSessionBackend` — rows in `buraq_sessions` table; clean with `python manage.py clearsessions`
- `buraq.contrib.sessions.backends.cache.CachedSessionBackend` — cache-backed; uses `SESSION_CACHE_ALIAS` (default `"default"`); expiry is automatic

**Syndication framework**
- `buraq.contrib.syndication.Feed` — class-based feed view with `items()`, `item_title()`, `item_description()`, `item_link()`, `item_pubdate()`, `item_author()`, `item_categories()`, `item_guid()` hooks
- `buraq.contrib.syndication.RssFeed` — RSS 2.0 renderer with Atom `self` link; `write()` returns XML string
- `buraq.contrib.syndication.Atom1Feed` — Atom 1.0 renderer
- `Feed.as_feed(feed_type="rss"|"atom")` — returns an ASGI view function for a given format

**Content Types — new methods**
- `ContentType.get_by_natural_key(app_label, model)` — look up a `ContentType` row by its natural key; raises `DoesNotExist` if not found
- `ContentType.model_class()` — return the Python class for a `ContentType` row by searching `INSTALLED_APPS`; returns `None` if not importable
- `GenericRelation` (`buraq.contrib.contenttypes.fields`) — reverse accessor for `GenericForeignKey`; declare on the target model; exposes async `all()`, `filter()`, `count()`, `create()` through `_GenericRelatedManager`

**Templates — app-directories loader**
- `APP_DIRS = True` setting (default) — `get_templates()` now scans every installed app's `templates/` subfolder and adds them to the Jinja2 `FileSystemLoader`; project-level `TEMPLATES_DIR` takes priority

**Templates — new Jinja2 globals**
- `regroup(iterable, grouper)` — group a sequence by an attribute; returns `[{"grouper": value, "list": [items]}, …]`
- `cycle(*values)` — returns a callable object that cycles through values on each call
- `ifchanged()` — returns a callable that is truthy only when its argument changes between successive calls
- `spaceless(html)` — removes whitespace between HTML tags

**Background Tasks**
- `buraq.contrib.tasks.background_task` — decorator that marks any async or sync function as a background task; decorated functions grow an `aenqueue()` method and still behave as normal callables
- `buraq.contrib.tasks.Task` — wrapper class returned by `@background_task`; exposes `aenqueue(*args, **kwargs)` with `_queue` / `_priority` per-call overrides
- `buraq.contrib.tasks.TaskResult` — dataclass returned by `aenqueue()`; fields: `id`, `status`, `return_value`, `exception`, `attempts`; `await result.arefresh()` fetches latest state from the backend
- `buraq.contrib.tasks.TaskStatus` — enum: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`
- `buraq.contrib.tasks.backends.base.BaseTaskBackend` — abstract base; implement `aenqueue()` + `aget_result()` for custom backends
- `buraq.contrib.tasks.backends.dummy.DummyBackend` — executes tasks immediately in-process; ideal for tests and development; results stored in memory
- `buraq.contrib.tasks.backends.db.DatabaseBackend` — persists tasks to `buraq_tasks` table; `buraq worker` polls and executes pending tasks; full status lifecycle (PENDING → RUNNING → SUCCEEDED / FAILED)
- `TASKS` setting — `{"default": {"BACKEND": "..."}}` — selects the active backend
- `buraq worker [--queue] [--concurrency] [--poll-interval] [--max-tasks]` — management command that runs the task worker process; polls `DatabaseBackend` for pending tasks and executes them concurrently; exits cleanly on `SIGINT`/`SIGTERM`

**Content Security Policy**
- `buraq.middleware.csp.ContentSecurityPolicyMiddleware` — ASGI middleware; adds `Content-Security-Policy` and/or `Content-Security-Policy-Report-Only` headers to every response based on `CONTENT_SECURITY_POLICY` / `CONTENT_SECURITY_POLICY_REPORT_ONLY` settings
- `CONTENT_SECURITY_POLICY` / `CONTENT_SECURITY_POLICY_REPORT_ONLY` settings — dicts of directives; directive names accept hyphens or underscores
- `CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES` — list of directives that receive an auto-generated per-request nonce; nonce available in templates as `{{ request.state.csp_nonce }}`
- `buraq.views.decorators.csp.csp_override(**directives)` — replace the enforced CSP for a single view; pass `None` to suppress the header entirely
- `buraq.views.decorators.csp.csp_report_only_override(**directives)` — override the report-only header for a single view
- `buraq.utils.csp.CSP` — programmatic CSP builder; `CSP(default_src=["'self'"], ...).as_header()` renders the header string; `nonce=True` generates a per-instance random nonce; `update(**overrides)` returns a new derived policy

**Auth Backends**
- `buraq.contrib.auth.backends.AllowAllUsersModelBackend` — like `ModelBackend` but skips the `is_active` check; authenticates inactive accounts (useful for "account disabled" post-login pages)
- `buraq.contrib.auth.backends.AllowAllUsersRemoteUserBackend` — remote-user backend that authenticates inactive users

**Model Fields**
- `buraq.orm.fields.GeneratedField(expression, output_field, db_persist=True)` — database-computed column; maps to SQLAlchemy `Computed`; `db_persist=True` creates a STORED column (PostgreSQL 12+, MySQL 5.7+, SQLite 3.31+); read-only in Python; exported from `buraq.models` and `buraq.orm`
- `buraq.orm.fields.CompositePrimaryKey(*fields)` — declare a multi-column primary key in `Meta.primary_key`; suppresses the implicit auto-increment `id` column; exported from `buraq.models` and `buraq.orm`

**Aggregates**
- `buraq.orm.aggregates.AnyValue(field)` — returns an arbitrary non-NULL value from the group; useful in `GROUP BY` queries where the column is functionally dependent on the key; native on MySQL 8.0.2+ and MariaDB 10.3+

**Test Utilities**
- `buraq.test.MessagesTestMixin` — mixin for `TestCase`; adds `assertMessages(response, expected, *, ordered=True)` to compare flash messages in a response by text (and optionally level)
- `buraq.test.captureOnCommitCallbacks(*, execute=False)` — context manager; patches `buraq.db.on_commit` to collect callbacks instead of waiting for a real commit; `execute=True` runs them immediately
- `buraq.contrib.staticfiles.storage.InMemoryStorage` — volatile in-memory storage backend; stores files as `bytes` in a dict; no disk I/O; `clear()` removes all stored files; ideal for tests

**Utils**
- `buraq.utils.csp` module — `CSP` class with `as_header()`, `nonce` property, and `update()` method
- `csp_nonce_attr(request)` Jinja2 global — renders `nonce="<value>"` when a CSP nonce is present on the request, empty string otherwise; registered automatically into every Jinja2 environment

**Cryptographic Signing**
- `buraq.utils.signing.Signer` — HMAC-SHA256 string signer; `sign(value)` / `unsign(signed_value)` / `sign_object(obj)` / `unsign_object(signed_value)`; configurable `key`, `sep`, `salt`, `algorithm`
- `buraq.utils.signing.TimestampSigner` — extends `Signer` with an embedded UTC timestamp; `unsign(signed_value, max_age=N)` raises `SignatureExpired` when the value is older than `max_age` seconds
- `buraq.utils.signing.dumps(obj, salt, compress)` — serialize any JSON-serializable object and return a signed URL-safe string
- `buraq.utils.signing.loads(s, salt, max_age)` — verify and deserialize; raises `BadSignature` or `SignatureExpired`
- `BadSignature` / `SignatureExpired` — importable directly from `buraq.utils.signing`

**Upcoming framework alignment**
- `DatabaseCache` — `CACHE_CULL_PROBABILITY` setting (default `0.1`) triggers automatic culling of expired entries on a percentage of writes; set to `0.0` to disable; prevents unbounded table growth without a scheduled job; read from settings at startup, overridable per-instance via the `cull_probability` constructor kwarg
- `BaseCommand.requires_settings` — new class attribute (`bool`, default `True`); when `True` (default), an `ImportError` from the settings module propagates at command startup; when `False`, the error is suppressed and the command runs without settings (useful for scaffold/init commands)
- `startproject` now generates `main.py` at the project root, re-exporting `app` from `config.urls`; this makes the default `buraq runserver` entry point (`main:app`) resolve correctly out of the box
- `listurls` management command — prints all URL patterns from the project's root URLconf; columns: path, view dotted name, route name; `--urlconf` selects a non-default URLconf module
- `import_string()` now supports top-level modules (e.g. `import_string("json")`) and submodules (e.g. `import_string("os.path")`); previously only attribute paths worked
- `JsonResponse` `safe` parameter now defaults to `False`; any JSON-serializable type is accepted without passing `safe=False` explicitly; pass `safe=True` to restrict top-level value to `dict`
- `BuraqJSONEncoder` (`buraq.utils.json`) — stdlib `json.JSONEncoder` subclass handling `datetime`, `date`, `time`, `timedelta`, `Decimal`, `UUID`; `datetime` and `time` objects with zero microseconds are serialized without the millisecond component (e.g. `"2026-01-01T12:00:00"` not `"2026-01-01T12:00:00.000"`)
- `pbkdf2()` default iteration count raised from 260,000 to 1,800,000 to match current security guidance
- `force_login()` (test client) — now skips authentication backends that do not implement `get_user()` or `aget_user()`; permission-only backends no longer cause `AttributeError` during forced login in tests

**Management commands**
- `version` — print the installed Buraq version string (`Buraq 0.1.0`)
- `findstatic <path> [--first]` — locate a static file by searching all configured `STATICFILES_FINDERS`; prints absolute path for each match; `--first` stops at the first result
- `testserver <fixture> ... [--port] [--host] [--no-input]` — flush the database, load one or more JSON fixture files, then start the development server; useful for manual QA with realistic data without touching production
- `sqlflush` — print the `DELETE` SQL statements that `flush` would execute, without running them; redirect output to generate a manual reset script
- `sqlsequencereset [app ...]` — print `SELECT setval(...)` SQL to reset PostgreSQL autoincrement sequences after bulk data imports; no-op on SQLite/MySQL
- `optimizemigration <revision1> <revision2> ... [--name]` — merge two or more divergent Alembic revision heads into one via `alembic merge`; requires at least two revision IDs; exits with an error if fewer than two are given
- `remove_stale_contenttypes [--no-input] [--include-stale-apps]` — delete `ContentType` rows for models that no longer exist; run after removing an app or model from `INSTALLED_APPS`
- `sqlmigrate <revision>` — print the SQL for an Alembic revision without executing it; `--backwards` shows the downgrade SQL
- `squashmigrations <start> <end>` — merge a range of Alembic revisions into one via `alembic merge`; `--name` controls the message
- `createcachetable [--table NAME]` — create the SQL table used by `DatabaseCache`
- `clearsessions` — delete all expired rows from the `buraq_sessions` table (database session backend)
- `test [paths] [--failfast] [--verbosity]` — run the test suite via pytest; sets `BURAQ_ENV=test` automatically

**Utils**
- `buraq.utils.__init__` — now re-exports all utility submodules so `from buraq.utils import signing`, `from buraq.utils import crypto`, etc. work without the full dotted path

**Signals**
- `pre_migrate` and `post_migrate` are now fired by the `migrate` and `rollback` management commands with a `revision` kwarg

**Views**
- `ListView.allow_empty = False` now enforced — raises `Http404` when the queryset is empty and `allow_empty` is set to `False`

**Template — Built-in Filters**
- `buraq/template/builtins.py` — 21 built-in Jinja2 filters registered automatically into every environment:
  - **Date/time:** `date`, `time`, `timesince`, `timeuntil`
  - **Text:** `truncatechars`, `truncatewords`, `truncatechars_html`, `wordcount`, `capfirst`, `addslashes`, `slugify`, `linenumbers`, `pluralize`, `yesno`, `default_if_none`, `phone2numeric`
  - **HTML:** `linebreaks`, `linebreaksbr`, `urlize`, `escapejs`, `json_script`
  - **Numbers/sizes:** `filesizeformat`, `floatformat`
- `date` filter supports the full date format code set: `d`, `j`, `D`, `l`, `S`, `m`, `n`, `M`, `N`, `F`, `Y`, `y`, `H`, `G`, `h`, `g`, `i`, `s`, `A`, `a`, `U`, `W`, `z`, `t`
- `timesince` / `timeuntil` return human-readable elapsed/remaining time up to 2 significant units
- `json_script(value, element_id)` safely embeds JSON data in a `<script type="application/json">` tag; HTML-special characters are Unicode-escaped to prevent XSS

**Template — Globals**
- `url(name, **kwargs)` global — calls `reverse()` from templates; crashes were silently obscuring missing registrations until this was wired
- `static(path)` global — prepends `STATIC_URL` to the given path
- `csrf_input(request)` global — returns `Markup('<input type="hidden" name="csrfmiddlewaretoken" value="...">')` ready for use inside `<form>` tags
- `csrf_token(request)` global — returns the raw CSRF token string for custom `<input>` rendering
- `STATIC_URL` and `MEDIA_URL` globals — available in every template without explicit context passing

**Template — Context Processors**
- `render()` in `buraq.shortcuts` now automatically calls `run_context_processors(request)` and merges results into the template context before rendering; caller-supplied keys override processor values; any processor error is silently ignored so rendering is never blocked

**Shortcuts**
- `get_list_or_404(model, **kwargs)` — fetches a filtered queryset and raises `HTTP 404` if the result is empty; mirrors `get_object_or_404` for list views

**URLs**
- `reverse_lazy(name, **kwargs)` — lazy URL reversal that is not evaluated until the result is used as a string; suitable for class-level `success_url` attributes and other places where the URL registry may not yet be populated at class definition time

**Utilities**
- `buraq.utils.module_loading` — `import_string(dotted_path)` loads any class or function by dotted Python path; `autodiscover_modules(*names)` imports `<app>.<name>` for every app in `INSTALLED_APPS` (signals, admin registrations, etc.)
- `buraq.utils.decorators` — `method_decorator(decorator, name="")` converts a function decorator for use on a class-based view method; handles async methods correctly
- `buraq.utils.datastructures` — `MultiValueDict` — a `dict` subclass that stores multiple values per key; `getlist(key)` returns all values, `getfirst(key)` returns the first, `appendlist(key, value)` appends without overwriting, `lists()` iterates `(key, [values])` pairs

**Signals**
- `m2m_changed` — fires `pre_add` / `post_add`, `pre_remove` / `post_remove`, `pre_clear` / `post_clear` around every `_M2MManager` operation; kwargs: `sender` (through table), `action`, `instance` (source model), `reverse=False`, `model` (target class), `pk_set` (set of affected PKs, or `None` for `clear`)
- `pre_migrate` / `post_migrate` — fired around migration runs; kwargs: `app_config`, `verbosity`, `interactive`, `using`
- `class_prepared` — fired after a model class body is fully prepared

**ORM — Signals**
- `pre_init` / `post_init` signals now fired inside `Model.__init__`; `pre_init` receives `args` and `kwargs` before the instance is built, `post_init` receives the completed `instance`
- `Signal.send_sync(sender, **kwargs)` — synchronous dispatch path for contexts where no async event loop is running (e.g. object construction); only fires non-coroutine receivers

**ORM — Lookups**
- `iso_year` lookup — filters by ISO 8601 year using `EXTRACT(isoyear …)`; e.g. `filter(published__iso_year=2025)`
- `iso_week_day` lookup — filters by ISO weekday (1=Monday … 7=Sunday) using `EXTRACT(isodow …)`
- `contained_by` lookup — PostgreSQL `<@` operator; tests that a JSON/array column is contained in the given value
- `has_key` lookup — PostgreSQL `?` operator; tests that a JSONB column contains a top-level key
- `has_keys` lookup — PostgreSQL `?&` operator; all keys in list must be present
- `has_any_keys` lookup — PostgreSQL `?|` operator; any key in list must be present
- `overlap` lookup — PostgreSQL `&&` operator; array/range column overlaps with the given value

**ORM — QuerySet**
- `QuerySet.union(*qs)` / `.intersection(*qs)` / `.difference(*qs)` — SQL `UNION` / `INTERSECT` / `EXCEPT` set operations; all delegate to SQLAlchemy `union`, `intersect`, `except_`
- `QuerySet.extra(select, where, params, tables)` — low-level escape hatch for raw SQL fragments; adds `SELECT` expressions, `WHERE` clauses, and extra `FROM` tables to the compiled query

**ORM — Model**
- `Model._state` — `_ModelState(adding=True/False)` attached to every instance; `adding` is `True` for unsaved instances and `False` after the first `save()`
- `Model.get_absolute_url()` — stub that raises `NotImplementedError`; override in subclasses to return the canonical URL for a model instance
- `Model.natural_key()` — stub that raises `NotImplementedError`; override to return a tuple that uniquely identifies the instance without its surrogate PK
- `RelatedManager` — async reverse FK / M2M accessor; `all()`, `filter()`, `create()`, `add()`, `remove()`, `clear()`, `set()`

**ORM — Fields**
- `SmallAutoField` — `SMALLSERIAL` / `INTEGER AUTOINCREMENT` primary key for tables with fewer than 32 768 rows
- `BigAutoField` — `BIGSERIAL` / `BIGINT AUTOINCREMENT` primary key; chosen automatically when `DEFAULT_AUTO_FIELD` is set

**ORM**
- `Aggregate(default=value)` — wraps the aggregate expression in `COALESCE(agg, default)` so queries return a defined value instead of `NULL` when the result set is empty (e.g. `Count("id", default=0)`)

**Forms**
- `SplitDateTimeField` — accepts a `(date_string, time_string)` two-element list and combines them into a `datetime.datetime`; available in `buraq.forms.fields`
- `BaseForm.as_p()` — render the form as `<p>` blocks with label, widget, and inline error list
- `BaseForm.as_table()` — render as `<tr>` rows (caller wraps in `<table>`)
- `BaseForm.as_div()` — render as `<div class="form-group">` blocks
- `BaseForm.as_ul()` — render as `<li>` items (caller wraps in `<ul>`)
- `ErrorList` / `ErrorDict` — list and dict subclasses for form error rendering; `ErrorList.as_ul()` returns an `<ul class="errorlist">` block; `ErrorDict.as_ul()` groups errors by field
- `BoundField.label_tag()` — returns the `<label>` HTML for a field, respecting `label_suffix`; `BoundField.css_classes(extra_classes)` — returns a space-joined string of CSS classes for the field wrapper
- `BaseFormSet` — collection of same-type forms; `is_valid()`, `save(commit=)`, `errors`, `management_form_html()`; `__iter__` and `__len__` for template iteration
- `BaseFormSet.can_order` — when `True`, each form gets an `ORDER` `IntegerField`; `formset.ordered_forms` returns forms sorted by that value
- `BaseFormSet.can_delete` — when `True`, each form gets a `DELETE` `BooleanField`; `formset.deleted_forms` returns forms marked for deletion; `cleaned_data` omits deleted forms automatically
- `SuccessMessageMixin` (`buraq.views.mixins`) — mixin for `FormView`/`CreateView`/`UpdateView`; set `success_message = "..."` (supports `%(field)s` placeholders from `cleaned_data`); override `get_success_message()` for dynamic messages; calls `buraq.contrib.messages.success()` after `form_valid()`
- `modelformset_factory(model, form, extra, max_num)` — returns a `BaseFormSet` subclass for editing multiple instances of a model
- `inlineformset_factory(parent_model, model, form, fk_name, extra, max_num)` — inline variant bound to a parent instance; stores `_fk_name` so callers can set the FK before saving with `commit=False`

**Auth Forms**
- `buraq.contrib.auth.forms.AuthenticationForm` — validates `username` + `password`; `await form.get_user(request)` returns the authenticated user or `None`
- `buraq.contrib.auth.forms.BaseUserCreationForm` — validates `username`, `password1`, `password2` (must match); `await form.save()` creates the user; subclass to add extra fields
- `buraq.contrib.auth.forms.SetPasswordForm` — sets a new password for a known user without requiring the old one; used in password-reset flows
- `buraq.contrib.auth.forms.PasswordChangeForm` — extends `SetPasswordForm` with an `old_password` field that must match the current password
- `buraq.contrib.auth.forms.AdminPasswordChangeForm` — sets any user's password without knowing the current one; intended for staff-only administration flows

**Auth — Class-Based Views**
- `LoginView` — renders a login form on GET; calls `authenticate()` then `login()` on POST (session-based); redirects to the `next` query parameter or `success_url`; template: `registration/login.html`
- `LogoutView` — calls `logout()` (flushes session, resets `request.user` to `AnonymousUser`) and redirects to `next_page`; template: `registration/logged_out.html`
- `PasswordChangeView` — authenticated POST endpoint for `old_password` + `new_password1` + `new_password2`; updates `hashed_password` on success; template: `registration/password_change_form.html`
- `PasswordResetView` — accepts an email address, generates a HMAC-SHA256–signed token (expires after 24 h), emails a reset link; silently succeeds even for unknown addresses to prevent user enumeration; template: `registration/password_reset_form.html`
- `PasswordResetConfirmView` — validates the signed token, verifies the HMAC, and updates the password; rejects expired or tampered tokens with a clear error message; template: `registration/password_reset_confirm.html`

**Testing**
- `buraq.test.DiscoverRunner` — test runner that discovers and runs tests using pytest; `run_tests(paths)` returns failure count; accepts `verbosity`, `failfast`, `keepdb` constructor arguments; used internally by `buraq test`
- `override_settings(**kwargs)` — context manager and decorator that temporarily replaces settings values; fires `setting_changed` signal on apply and restore; handles both sync and async test functions; exported from `buraq.test`
- `SimpleTestCase.assertFormError(form, field, errors)` — asserts that a form field (or `None` for non-field errors) contains the expected error string(s)
- `SimpleTestCase.assertHTMLEqual(html1, html2)` — compares two HTML strings after collapsing whitespace
- `SimpleTestCase.assertRaisesMessage(exc_class, message)` — context manager that asserts the given exception is raised and its string representation contains `message`

**Management Commands**
- `shell` — interactive Python shell (`code.interact`) with all model classes from `INSTALLED_APPS` and `SessionLocal` pre-imported; `--command/-c` runs a Python expression and exits
- `check` — runs all registered system checks and prints results with severity labels; exits with code 1 on errors
- `dbshell` — opens the native database CLI (`sqlite3`, `psql`, or `mysql`) for the configured `DATABASE_URL`; connection args are derived from the URL
- `dumpdata` — serialises all database tables to JSON; `--output/-o` writes to a file; `--exclude/-e` skips named tables; timestamps and binary values are serialised via `str()`
- `loaddata` — reads a JSON fixture file and bulk-inserts rows into the matching tables; `--table/-t` restricts which tables to load
- `flush` — deletes all rows from every table in reverse dependency order without dropping the schema; requires explicit confirmation unless `--no-input`
- `changepassword` — prompts for a new password (with confirmation) for the named user and updates `hashed_password` via `hash_password()`
- `inspectdb` — introspects the live database schema and prints model class stubs to stdout; `--table/-t` restricts output; redirect to `models.py` to bootstrap a project from an existing database
- `diffsettings` — compares current settings against defaults and prints changed values marked with `###`; `--all` shows every setting
- `sendtestemail` — sends a plain-text test email to the given address using the configured email backend; useful for verifying `EMAIL_HOST`, `EMAIL_PORT`, and credentials without writing a view

**ORM — Expressions & Functions**
- `buraq.orm.expressions` — `Case`, `When`, `Value`, `OuterRef`, `Subquery`, `Exists`, `ExpressionWrapper` for conditional queries and correlated subqueries
- `buraq.orm.functions` — 70+ database functions: date/time (`Now`, `TruncDate`, `TruncTime`, `TruncMonth`, `TruncYear`, `ExtractYear`, …), string (`Concat`, `Upper`, `Lower`, `Trim`, `Replace`, `Substr`, `LPad`, `Collate`, …), math (`Abs`, `Ceil`, `Floor`, `Round`, `Sqrt`, `Exp`, `Pi`, `Cot`, `Power`, …), NULL handling (`Coalesce`, `NullIf`, `Greatest`, `Least`), type casting (`Cast`), hash (`MD5`, `SHA1`, `SHA256`, `SHA512`), UUID (`UUID4`, `UUID7`)
- `TruncTime(field)` — cast a datetime column to its time component
- `Exp(field)` — e raised to the column value
- `Pi()` — the π constant (no field argument)
- `Cot(field)` — cotangent
- `Collate(field, collation)` — apply a named collation for locale-aware ordering (e.g. `"und-x-icu"` on PostgreSQL)
- `buraq.orm.window` — window function support: `Window`, `RowNumber`, `Rank`, `DenseRank`, `PercentRank`, `CumeDist`, `Ntile`, `Lag`, `Lead`, `FirstValue`, `LastValue`, `NthValue`

**ORM — QuerySet**
- `Q.__xor__` — XOR set operation on Q objects (emulated as `(A OR B) AND NOT (A AND B)` for full database compatibility)
- `QuerySet.select_for_update(nowait, skip_locked)` — `SELECT … FOR UPDATE` row-level locking
- `QuerySet.earliest(*fields)` / `.latest(*fields)` — first/last object by field
- `QuerySet.last()` — return last object by primary key
- `QuerySet.dates(field, kind)` / `.datetimes(field, kind)` — distinct date/datetime values
- `QuerySet.raw(sql, params)` — raw SQL with named parameters, returns list of dicts
- `QuerySet.distinct()` — remove duplicate rows from results
- `QuerySet.select_related(*fields)` — JOIN-load FK/OneToOne relations in a single query
- `QuerySet.prefetch_related(*fields)` — subquery-load M2M/reverse FK relations
- `QuerySet.get_or_create(defaults, **kwargs)` — fetch or insert; returns `(instance, created)`
- `QuerySet.update_or_create(defaults, **kwargs)` — fetch-and-update or insert; returns `(instance, created)`
- `QuerySet.bulk_update(objs, fields)` — update specific fields on a list of instances in bulk
- `QuerySet.defer(*fields)` — load only specific columns; remaining columns fetched on access via SQLAlchemy `defer()`
- `QuerySet.only(*fields)` — load a named subset of columns via SQLAlchemy `load_only()`
- `QuerySet.explain(analyze, verbose)` — dialect-aware `EXPLAIN` output for query-plan debugging
- `QuerySet.alias(name)` — named subquery alias for reuse across multiple `filter()` / `annotate_expr()` calls

**ORM — Fields**
- `PositiveBigIntegerField` — big integer with `>= 0` constraint
- `DurationField` — maps Python `timedelta` to database `INTERVAL`
- `GenericIPAddressField` — IPv4/IPv6 with `protocol` option
- `DB_CASCADE`, `DB_SET_NULL`, `DB_SET_DEFAULT` FK delete-mode constants — signal database-engine-level `ON DELETE` with no Python callbacks; exported from `buraq.models` and `buraq.orm.fields`

**ORM — Model validation**
- `Model.full_clean()` — runs `clean_fields()` → `clean()` → `validate_unique()` in order; raises `ValidationError` listing all failures
- `Model.clean_fields(exclude)` — validates per-field values; respects `exclude` list
- `Model.clean()` — override hook for cross-field validation logic
- `Model.validate_unique(exclude)` — checks `unique=True` fields and `unique_together` constraints against the database

**ORM — Prefetch**
- `Prefetch(field, queryset, to_attr)` — pass to `prefetch_related()` for filtered or ordered prefetch querysets; `to_attr` stores results under a custom attribute; importable from `buraq.models`

**ORM — Fetch modes for deferred field access**
- `FETCH_ONE`, `FETCH_PEERS`, `FETCH_RAISE` — constants controlling deferred-field access strategy; importable from `buraq.orm.manager`
- `QuerySet.fetch_mode(mode)` — set the fetch strategy for all instances returned by `all()`: `FETCH_ONE` reloads each instance individually, `FETCH_PEERS` reloads all peers in a single batch query, `FETCH_RAISE` raises `FieldFetchBlocked` on any deferred-field access
- `FieldFetchBlocked` — exception raised when `FETCH_RAISE` is active and a deferred field is accessed; importable from `buraq.orm.manager`
- `QuerySet.totally_ordered` — read-only property; returns `True` when the queryset's `ORDER BY` clause includes the model's primary key (or another unique column), guaranteeing a stable, deterministic page-by-page iteration order

**ORM — in_bulk() values/values_list support**
- `Manager.in_bulk(id_list)` — now correctly handles querysets that have been narrowed with `values()` or `values_list()`, returning a `{pk: dict}` or `{pk: tuple}` mapping respectively

**ORM — Expressions**
- `JSONNull` (`buraq.orm.expressions`) — explicit JSON scalar `null` expression; renders as `CAST(NULL AS JSON)`; distinct from SQL `NULL` so JSON columns can store the JSON null value without ambiguity

**ORM — Database functions**
- `UUID4` (`buraq.orm.functions`) — generates a version-4 UUID at the database level via `gen_random_uuid()` (PostgreSQL) or equivalent
- `UUID7` (`buraq.orm.functions`) — generates a version-7 (time-ordered) UUID via `uuid_generate_v7()` on PostgreSQL; falls back to `gen_random_uuid()` on other databases

**ORM — Aggregates**
- `BitAnd(field)` — bitwise AND across all values; maps to `bit_and()` on supporting databases
- `BitOr(field)` — bitwise OR across all values; maps to `bit_or()`
- `BitXor(field)` — bitwise XOR across all values; maps to `bit_xor()`

**Sessions**
- `SessionBase.__bool__()` — session instances are now truthy when the session cache contains data and falsy when empty or not yet loaded; allows simple `if session:` guards

**Forms**
- `BLANK_CHOICE_LABEL` — constant `"---------"` for the default empty/blank select option; importable from `buraq.forms.forms`
- `Stylesheet` (`buraq.forms.forms`) — CSS path descriptor with custom HTML attributes for `Media`; pass as a member of `Media.css` lists alongside plain string paths; `Stylesheet(path, attrs={…}).render(medium)` emits a `<link>` tag with the provided attributes
- `FilePathField.set_choices()` — rescans the directory and refreshes `self.choices` on demand; useful for long-running processes where the directory contents change after form class creation

**Auth**
- `Permission.user_perm_str` — read-only property on `Permission` instances; returns the permission string in the `"<app_label>.<codename>"` format expected by `User.has_perm()`

**Views**
- `RedirectView.preserve_request = True` — returns `307 Temporary Redirect` (or `308 Permanent Redirect` when `permanent=True`) instead of `302`/`301`; instructs the client to repeat the request with the same HTTP method rather than downgrading to `GET`
- `RedirectView.put()`, `.patch()`, `.delete()` — now explicitly handled alongside `get()` and `post()` so that method-preserving redirects work for non-GET verbs

**Utils**
- `parse_duration()` — now parses ISO 8601 week-only period strings: `P2W`, `P1.5W`, `-P3W`, etc.; previously only parsed them as part of a full `PnYnMnWnDTnHnMnS` string

**Auth**
- `Permission`, `Group`, `UserGroup`, `UserPermission`, `GroupPermission` models (`buraq.contrib.auth.models`)
- `User.has_perm(perm)`, `User.has_perms(perms)`, `User.has_module_perms(app)` — async permission checks with in-memory result caching; `_invalidate_perm_cache()` clears cached results
- `User.groups()`, `User.user_permissions()` — async relation accessors
- `make_password()`, `check_password()`, `validate_password()`, `update_session_auth_hash()` — password utilities (`buraq.contrib.auth`)
- `buraq.contrib.auth.backends.ModelBackend` — default username/password backend
- `AUTHENTICATION_BACKENDS` setting (default: `["buraq.contrib.auth.backends.ModelBackend"]`)
- `authenticate()` iterates all configured backends; stamps `user._auth_backend` with the winning backend path
- `_clear_backend_cache()` — invalidates the cached backend list at runtime
- `buraq.contrib.auth.password_validation` — `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`, `UserAttributeSimilarityValidator`, `MaximumLengthValidator`; `validate_password(password, user)` and `get_password_validators()` helpers; configurable via `AUTH_PASSWORD_VALIDATORS` setting

**Exceptions**
- `SuspiciousFileOperation` — subclass of `SuspiciousOperation`; raised by `FileSystemStorage` when a file name would escape the storage root

**Views**
- `FormView` — generic class-based view for displaying and processing a single form
- `LoginRequiredMixin`, `PermissionRequiredMixin`, `UserPassesTestMixin`, `AccessMixin` — auth mixins for class-based views (`buraq.views.mixins`)
- `@user_passes_test(fn)` — decorator that calls `fn(user)` and redirects on failure
- `@cache_page(timeout)` — full-response cache decorator; uses active cache backend
- `WeekArchiveView`, `DayArchiveView`, `TodayArchiveView`, `ArchiveIndexView`, `DateDetailView` — date-based archive views

**Middleware**
- `GZipMiddleware` (`buraq.middleware.gzip`) — ASGI middleware that gzip-compresses responses larger than a configurable threshold; respects `Accept-Encoding: gzip`; skips already-compressed content types
- `ConditionalGetMiddleware` (`buraq.middleware.common`) — sets `ETag` and `Last-Modified` headers; returns `304 Not Modified` when the request carries a matching `If-None-Match` or `If-Modified-Since` header
- `MessageMiddleware` (`buraq.middleware.common`) — persists flash messages across redirects; stores messages in the session between requests
- `BrokenLinkEmailsMiddleware` (`buraq.middleware.common`) — emails `MANAGERS` when a 404 is returned for a request originating from an internal `Referer`; silent no-op when `MANAGERS` is empty

**Paginator**
- `buraq.paginator.AsyncPaginator` — explicit async-only variant of `Paginator`; always awaits the queryset count before slicing; returns `AsyncPage` instances
- `buraq.paginator.AsyncPage` — subclass of `Page` returned by `AsyncPaginator`; same navigation API (`has_next()`, `next_page_number()`, etc.)

**HTTP Responses**
- `buraq.http.FileResponse` — serve a file from disk with automatic `Content-Type` (guessed via `mimetypes`) and `Content-Disposition` header; `as_attachment=True` (default) triggers a download; `as_attachment=False` renders inline; `filename` overrides the download name

**HTTP Caching Decorators**
- `@condition(etag_func, last_modified_func)` — returns `304 Not Modified` based on ETag and/or Last-Modified callbacks; both sync and async callables supported; sets the corresponding response headers for cache-friendly GETs
- `@conditional_page` — zero-config ETag computed from MD5 of the response body; returns `304` when the client already has the current version; use `@condition` when you can compute the ETag cheaply before the view runs

**PostgreSQL Aggregates**
- `BoolAnd(field)` — `True` if all non-null values are true
- `BoolOr(field)` — `True` if any non-null value is true
- `Corr(y, x)` — Pearson correlation coefficient
- `CovarPop(y, x)` — population covariance
- `CovarSamp(y, x)` — sample covariance
- `RegrAvgX(y, x)`, `RegrAvgY(y, x)` — averages of the independent and dependent variables
- `RegrCount(y, x)` — number of rows where both inputs are non-null
- `RegrIntercept(y, x)` — Y-intercept of the least-squares-fit line
- `RegrR2(y, x)` — R² (coefficient of determination)
- `RegrSlope(y, x)` — slope of the least-squares-fit line
- `RegrSXX(y, x)`, `RegrSXY(y, x)`, `RegrSYY(y, x)` — sums of squares and cross products for regression

**URLs**
- `re_path(pattern, view, kwargs, name)` — register a route with a raw regex pattern instead of a path converter string
- `resolve(path)` — reverse-resolve a URL path to a `ResolverMatch`; raises `Resolver404` if no pattern matches
- `ResolverMatch` — named tuple-like result of `resolve()`; attributes: `func`, `args`, `kwargs`, `url_name`, `app_name`
- `Resolver404` — exception raised by `resolve()` when no pattern matches the given path
- `NoReverseMatch` — exception raised by `reverse()` when the named URL cannot be constructed from the given arguments

**Auth**
- `PasswordResetTokenGenerator` (`buraq.contrib.auth`) — generates and validates HMAC-SHA256–signed, time-limited tokens for password-reset links; `make_token(user)` → token string; `check_token(user, token)` → `bool`; configurable `PASSWORD_RESET_TIMEOUT` in seconds (default 86 400)

**CSRF**
- `CsrfViewMiddleware` — full ASGI class-based CSRF middleware; add to `MIDDLEWARE` list; validates `X-CSRFToken` header or `csrfmiddlewaretoken` POST field on unsafe methods; sets `csrftoken` cookie on every response; buffers and replays the request body when reading a form POST so the view still receives it
- `buraq.contrib.csrf` — `get_token(request)`, `@csrf_protect`, `@ensure_csrf_cookie`

**Forms**
- `RadioSelect` widget — renders radio button list, one per choice
- `CheckboxSelectMultiple` widget — renders checkbox list, multiple selections
- `MultipleHiddenInput` widget — renders multiple hidden inputs for list values (used by formsets)
- `ModelChoiceField` — single model instance picker from a queryset
- `ModelMultipleChoiceField` — multi-select model picker with `fetch_many()`
- `TypedMultipleChoiceField` — `MultipleChoiceField` with type coercion
- `buraq.forms.formsets` — `BaseFormSet`, `BaseModelFormSet`, `BaseInlineFormSet`; `formset_factory`, `modelformset_factory`, `inlineformset_factory`

**Email**
- `InMemoryEmailBackend` (`buraq.contrib.email.backends.locmem.EmailBackend`) — test backend that stores all sent messages in a module-level `outbox` list instead of delivering them; thread-safe via `threading.Lock`; set `EMAIL_BACKEND = "buraq.contrib.email.backends.locmem.EmailBackend"` in tests; import `outbox` / `clear_outbox()` to inspect or reset
- `EmailMultiAlternatives` — `EmailMessage` subclass for sending a single message with both `text/plain` and `text/html` bodies; `.attach_alternative(content, mimetype)` adds each part
- `mail_admins(subject, message)` — send email to all `ADMINS` in settings
- `mail_managers(subject, message)` — send email to all `MANAGERS` in settings

**Multiple Mailers**
- `MAILERS` setting — dict of named email backend configurations
- `get_connection(using=None)` — returns named backend from `MAILERS`, falls back to `EMAIL_BACKEND`; backends are cached after first instantiation
- `send_mail()`, `send_mass_mail()`, `mail_admins()`, `mail_managers()`, `send_template_mail()` all accept `using=` to select a specific mailer

**Validators**
- `BaseValidator` — base class for limit-based validators
- `StepValueValidator` — validate that a value is a multiple of a given step
- `validate_integer()`, `validate_ipv4_address()`, `validate_ipv6_address()`, `validate_ipv46_address()`
- `validate_image_file_extension()` — validate uploaded image file types
- `FileExtensionValidator(allowed_extensions)` — validate arbitrary file extensions
- `int_list_validator(sep, allow_negative)` — validate comma-separated integer strings

**File Storage**
- `buraq.core.files` — `File`, `ContentFile`, `UploadedFile` wrappers
- `FileSystemStorage(location, base_url)` — async `save`, `open`, `delete`, `exists`, `size`, `listdir`; path-traversal protection via `realpath()`; auto-suffixes on name collision
- `default_storage` — lazy proxy to configured `DEFAULT_FILE_STORAGE` backend
- `UploadedFile.from_starlette(upload)` — build from Starlette `UploadFile`

**System Checks**
- `buraq.checks` — startup validation framework: `@register` decorator, `run_checks()`, `run_checks_or_raise()`, message classes `Debug` / `Info` / `Warning` / `Error` / `Critical`
- Built-in checks: `SECRET_KEY` strength (`security.E001`, `security.W001`), `DEBUG + ALLOWED_HOSTS` safety (`security.W002`), SQLite in production (`database.W001`)

**Security Middleware**
- `buraq.middleware.SecurityMiddleware` — ASGI middleware that injects security headers on every response: `Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Permissions-Policy`; optional HTTP→HTTPS redirect via `SECURE_SSL_REDIRECT`
- New settings: `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`, `SECURE_SSL_REDIRECT`, `SECURE_PERMISSIONS_POLICY`, `X_FRAME_OPTIONS`

**Template Context Processors**
- `buraq.template.context_processors` — `request`, `auth`, `debug`, `i18n` processors; `run_context_processors(request)` merges all configured processors into a single context dict
- New setting: `TEMPLATE_CONTEXT_PROCESSORS` (defaults to `request` + `auth`)

**Content Types**
- `buraq.contrib.contenttypes.models.ContentType` — maps `app_label + model` to a unique ID for generic relations
- `buraq.contrib.contenttypes.fields.GenericForeignKey` — descriptor that resolves `(content_type_id, object_id)` to any model instance asynchronously

**Flatpages**
- `buraq.contrib.flatpages.models.FlatPage` — database-backed static content pages with `url`, `title`, `content`, `template_name`, `registration_required`
- `buraq.contrib.flatpages.views.flatpage` — async view that serves a `FlatPage` by URL path

**Redirects**
- `buraq.contrib.redirects.models.Redirect` — database-driven URL redirect rules (`old_path` → `new_path`; empty `new_path` returns 410 Gone)
- `buraq.contrib.redirects.middleware.RedirectFallbackMiddleware` — intercepts 404 responses and checks the `Redirect` table; validates `new_path` is relative before redirecting

**Sites**
- `buraq.contrib.sites.models.Site` — multi-domain support; `Site.get_current(request)` resolves the current domain from the Host header

**App Registry**
- `buraq.apps.AppConfig` — base class for application configuration with `name`, `verbose_name`, `label`, `async ready()` hook
- `buraq.apps.apps` — global `Apps` registry; `populate(INSTALLED_APPS)`, `run_ready_hooks()`, `get_app_config(label)`, `is_installed(app_name)`

**PostgreSQL**
- `buraq.contrib.postgres.fields` — `JSONField` (JSONB), `ArrayField` (ARRAY), `HStoreField` (hstore) column types for SQLAlchemy models
- `CITextField` / `CICharField` / `CIEmailField` — case-insensitive text columns backed by `CITEXT` (requires `CREATE EXTENSION IF NOT EXISTS citext`)
- `IntegerRangeField` / `BigIntegerRangeField` / `DecimalRangeField` / `DateRangeField` / `DateTimeRangeField` — PostgreSQL native range type columns (`int4range`, `int8range`, `numrange`, `daterange`, `tstzrange`)
- `GinIndex` / `GistIndex` / `BrinIndex` / `SpGistIndex` / `BloomIndex` / `HashIndex` — helper functions returning a correctly configured `sqlalchemy.Index` with the matching `postgresql_using=` option; pass to `Meta.indexes`
- `TrgmIndex(name, *columns, index_type="gin")` — trigram index using the `pg_trgm` extension; enables fast `LIKE`, `ILIKE`, and similarity (`%`) queries; `index_type` can be `"gin"` (default) or `"gist"` (better for `ORDER BY similarity`); requires `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- `buraq.contrib.postgres.search` — `SearchQuery`, `SearchVector`, `SearchRank`; all use `plainto_tsquery` for safe user input
- `buraq.contrib.postgres.aggregates` — `ArrayAgg`, `StringAgg`, `JsonAgg`, `BitAnd`, `BitOr`
- `buraq.contrib.postgres.functions` — `Unaccent`, `Now`, `Random`

**Testing**
- `SimpleTestCase.assertNumQueries(n)` — context manager; asserts exactly `n` SQL queries are executed in the block; records queries via SQLAlchemy event hook
- `SimpleTestCase.assertInHTML(needle, haystack, count=None)` — asserts that an HTML fragment appears (optionally exactly `count` times) inside a larger HTML string; whitespace-normalised comparison
- `SimpleTestCase.assertFormsetError(formset, form_index, field, errors)` — asserts that a specific form in a formset has the given error(s) on a field (or `None` for non-field errors)
- `LiveServerTestCase` — spins up a real ASGI server on a random port in a background thread; `self.live_server_url` gives the base URL; server is started in `setUpClass` and torn down in `tearDownClass`
- `buraq.test.AsyncClient` — exercises the full ASGI stack in-process; `get`, `post`, `put`, `patch`, `delete`, `head`, `options`; `json=` shorthand; `headers=` injection; `follow_redirects=`; `force_login(user)`
- `buraq.test.RequestFactory` — builds `starlette.requests.Request` objects for unit-testing individual views
- `buraq.test.TestCase` — async-aware `unittest.TestCase` with `asyncSetUp`/`asyncTearDown`; assertion helpers: `assertContains`, `assertNotContains`, `assertRedirects`, `assertStatusCode`, `assertJSONEqual`
- `buraq.test.SimpleTestCase` — assertion helpers without database or client
- `buraq.test.TransactionTestCase` — same as `TestCase`, documented for transaction-isolated tests

**Utilities**
- `buraq.utils.choices` — `TextChoices` and `IntegerChoices` enum base classes with `.choices`, `.labels`, `.values`, `.names` class properties
- `buraq.utils.feedgenerator` — `Rss201rev2Feed` (RSS 2.0.1) and `Atom1Feed` (Atom 1.0) feed generators; pure stdlib
- `buraq.utils.html` — `SafeString`, `mark_safe`, `escape`, `escapejs`, `conditional_escape`, `format_html`, `format_html_join`, `linebreaks`, `strip_tags`, `urlize`
- `buraq.utils.encoding` — `force_str`, `smart_str`, `force_bytes`, `iri_to_uri`, `uri_to_iri`, `escape_uri_path`
- `buraq.utils.crypto` — `get_random_string`, `constant_time_compare`, `pbkdf2`, `salted_hmac`
- `buraq.utils.functional` — `cached_property`, `LazyObject`, `SimpleLazyObject`, `lazy`, `classproperty`
- `buraq.utils.dateparse` — `parse_date`, `parse_time`, `parse_datetime`, `parse_duration` — ISO 8601 + `DD HH:MM:SS` formats
- `buraq.contrib.humanize` — `intcomma`, `ordinal`, `apnumber`, `pluralize`, `naturalday`, `naturaltime`, `naturalduration`, `intword`
- `buraq.serializers` — serialize querysets and model instances to JSON, Python, XML, or YAML; JSON backend uses `orjson` with stdlib fallback
- YAML serializer (`buraq.serializers.yaml.YamlSerializer`) — round-trips model data to YAML via PyYAML; registered under `"yaml"` format; `pip install pyyaml` required
- `BaseSerializer.load(data)` — deserializes and upserts records into the database; finds existing rows by PK or creates new instances; returns the list of saved model objects
- `deserialize_objects(format, data)` (`buraq.serializers`) — convenience async function that calls `deserialize()` then reconstructs model instances from the resulting record dicts

**Settings**
- `AUTH_PASSWORD_VALIDATORS` — pre-configured with `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`

**Management commands**
- `listurls` — prints a table of all registered routes with path, HTTP methods, and route name; accepts `--app module:obj`

**Cache**
- Redis `get_many` / `set_many` optimised — `get_many()` uses a single `MGET` command; `set_many()` uses a pipeline (previously one round-trip per key)

### Fixed

- **`management/cli.py` — `runserver` rejected IP host:port syntax** — the condition `"." not in bind.split(":")[0]` treated `0.0.0.0:8001` as a module path because IP addresses contain dots; replaced with a digit-check on the port portion so any `host:port` where the port is numeric is parsed correctly
- **`management/cli.py` — `test --pattern` prevented tests from running** — `--collect-only` was appended to pytest args when a custom pattern was given, causing pytest to discover but never execute tests; replaced with `--ignore-glob`
- **`management/cli.py` — `testserver` bind argument was unreachable** — the `fixtures` list argument consumed all positional input, leaving the `bind` positional argument permanently unreachable; `bind` is now an `--app` option
- **`management/cli.py` — `optimizemigration` always failed with a single revision** — `alembic merge` requires two or more revision IDs; passing a single revision raised an Alembic error every time; the command now accepts a list of revisions and exits with a clear error if fewer than two are provided

- **`contrib/cache/backends/base.py` — sequential N-RTT loops in batch operations** — `get_many()`, `set_many()`, and `delete_many()` awaited each key serially; replaced with `asyncio.gather()` so all operations execute concurrently
- **`contrib/cache/backends/memory.py` — `asyncio.Lock()` created before event loop** — the lock was instantiated in `__init__`, before an event loop existed, raising `RuntimeError` in some startup paths; replaced with a lazy `_get_lock()` method that creates the lock on first use
- **`contrib/auth/views.py` — `NameError` on `obtain_auth_token` and `get_me`** — both functions referenced `create_access_token` and `get_current_user_id` which were removed in a prior cleanup; calling either view raised `NameError` at runtime; both functions removed; `LoginView.post()` and `LogoutView.get()` rewritten to use session-based `authenticate()` / `login()` / `logout()`
- **`contrib/auth/__init__.py` — discarded `asyncio.create_task()` reference** — `login()` called `asyncio.create_task(_update_last_login())` without storing the return value; if the background task raised, Python emitted an unraisable "Task exception was never retrieved" warning; the task is now stored and a `done_callback` attached to log failures
- **`contrib/email/message.py` — `get_backend()` does not exist** — `EmailMessage.send()` imported `get_backend` from `buraq.contrib.email.send`; the function is named `get_connection`; all sends raised `ImportError`
- **`contrib/email/message.py` — `EmailMultiAlternatives` silently dropped attachments** — `build_mime()` only assembled the `alternative` part (plain + HTML) and ignored `self.attachments`; fixed by wrapping the `alternative` block in a `mixed` outer container when attachments are present
- **`contrib/cache/backends/db.py` — SQL named-parameter type mismatch** — `_execute()` built the binding dict with integer keys (`{0: value}`) via `dict(enumerate(params))`, but the `:0` placeholders in the SQL require string keys; fixed by casting with `{str(i): v for i, v in enumerate(params)}`
- **`contrib/cache/backends/db.py` — non-atomic DELETE + INSERT in `set()`** — `set()` opened two separate `_execute()` calls (one to delete, one to insert), each auto-committing independently; a crash between them left no entry in the table; both statements now share one `SessionLocal()` context with a single commit
- **`orm/transaction.py` — `ContextVar` leak on commit failure** — if the transaction committed then a post-commit callback raised, `_current_session` and `_on_commit_callbacks` were left set for the remainder of the request; both are now reset inside a `finally` block regardless of outcome
- **`orm/transaction.py` — sync callback returning a coroutine was not awaited** — a callback registered as a lambda wrapping an async function (e.g. `lambda: async_fn(arg)`) returned a coroutine object from the sync branch; the coroutine was discarded silently; `inspect.iscoroutine(result)` now detects and awaits it
- **`middleware/csp.py` — `csp_override(None)` did not suppress CSP header** — `getattr(request.state, "_csp_override", None)` returned `None` both when the decorator was not applied and when it was explicitly applied with `None` to suppress the header; a module-level `_UNSET = object()` sentinel now distinguishes the two states
- **`contrib/sessions/backends/file.py` — blocking file I/O on the async event loop** — `load()`, `save()`, `delete()`, `exists()`, and `clear_expired()` all called `Path` I/O methods directly on the event loop, blocking it for each disk operation; all I/O is now wrapped in `asyncio.to_thread()`; `clear_expired()` is now `async def`
- **`User` concrete model missing `check_password` / `set_password`** — the concrete `User` class in `contrib/auth/models.py` does not inherit from `AbstractBaseUser`, so it had no password-checking methods; `check_password(raw_password)` and `set_password(raw_password)` are now defined directly on `User`, delegating to `verify_password` / `hash_password` from `buraq.contrib.auth._passwords`; the admin login was silently failing as a result
- **`createsuperuser` used raw SQLAlchemy session** — the command called `db.add(user)` + `db.commit()` directly on a Buraq model, which bypasses the ORM layer and fails; replaced with `User.objects.create()`

- **`refresh_from_db(fields=...)` was a no-op** — the `fields` parameter was accepted but ignored; the method always reloaded all columns. It now issues a `SELECT` limited to the requested columns and updates only those attributes on the instance.
- **`Model.save()` returned stale data** — after an `UPDATE`, `save()` returned the pre-update Python object while the database row held the new values. The merged SQLAlchemy instance is now synced back to `self` so all columns reflect the committed state.
- **`save()` bypassed `atomic()` transactions** — `save()` always opened its own session, so a `save()` call inside `async with atomic():` ran in a separate transaction. `save()` now checks `_current_session` (a `ContextVar` set by `atomic()`) and participates in the outer session when one is active.
- **`on_commit()` ran immediately** — callbacks executed inside the `atomic()` block before the transaction committed, so they ran even when the transaction rolled back. Callbacks are now collected in `_on_commit_callbacks` (a `ContextVar`) and executed only after `commit()` succeeds; discarded on rollback.
- **`get_or_create` / `update_or_create` race condition** — both used a check-then-create pattern with a TOCTOU gap. Both now use try-create-catch-`IntegrityError`.
- **`bulk_create` dialect detection** — dialect was detected by string-matching `DATABASE_URL`, which failed for `postgresql+asyncpg://` URLs. Changed to `make_url(settings.DATABASE_URL).get_dialect().name`.
- **`bulk_update` N+1 queries** — issued one `UPDATE` per instance. Replaced with a single parameterised statement using `sa.bindparam` bulk binding; one round-trip regardless of batch size.
- **`_M2MManager.add()` duplicate inserts** — did not guard against concurrent inserts of the same M2M pair. Changed to `INSERT … ON CONFLICT DO NOTHING` (dialect-aware; falls back on MySQL).
- **`_M2MManager.set()` non-atomic** — called `clear()` then `add()` in separate sessions, leaving a window where the relation was empty. Both now share a single session.
- **`OuterRef` in subqueries was unresolved** — `OuterRef("field")` produced a placeholder that was never replaced with the actual outer-model column. `_resolve_lookup` now stores a recognisable `column("__outerref__field")` placeholder; `Subquery._replace_outer_refs()` uses `sqlalchemy.sql.visitors.cloned_traverse` to substitute real outer columns before SQL compilation.
- **`PositiveIntegerField` / `PositiveBigIntegerField` column name** — `to_sa_column()` defaulted to `name="value"`, mapping every instance of these fields on the same model to the same column. Default changed to `name=""`.
- **`PositiveSmallIntegerField` missing constraint** — declared a `SMALLINT` column with no `CHECK` constraint, so negative values were accepted. A `CHECK (col >= 0)` constraint is now added.
- **`cache_page` imported non-existent `get_cache`** — caused an `ImportError` on first use. Changed to import the `cache` singleton directly.
- **`BaseValidator.compare` identity check** — used `is not` instead of `!=`, raising `ValidationError` only when Python objects were not the same instance. Changed to `!=`.
- **`AuthenticationMiddleware` swallowed unexpected exceptions** — caught all `Exception` types and silently set `request.user = AnonymousUser()`. Now catches only `DoesNotExist` and `ValueError`; all others are logged at `ERROR` level.
- **`rollback` / `showmigrations` ignored subprocess failure** — did not check the subprocess return code, reporting failed Alembic commands as success. Both now raise `SystemExit(1)` on non-zero exit.
- **`_run_async` used deprecated `asyncio.get_event_loop()`** — deprecated in Python 3.10, errors in 3.12+. Changed to a `ThreadPoolExecutor` with `asyncio.run()` in a fresh thread.
- **Signals `weak=True` stored strong references** — `Signal.connect()` accepted `weak=` but stored strong references regardless. Weak-reference support now works correctly via `weakref.ref` / `weakref.WeakMethod`; dead references are pruned on dispatch.
- **`Signal.connect()` `dispatch_uid` was ignored** — deduplication key was stored but never checked on subsequent calls, allowing the same handler to be registered multiple times. Registering with an existing `dispatch_uid` now replaces the entry.
- **`QuerySet.using()` silently did nothing** — returned `self` unchanged. Now raises `NotImplementedError` with an explanatory message.
- **System check errors did not abort startup** — `Error`-level messages were printed but did not prevent the app from starting. `registry.run_checks_or_raise()` is now called in `_on_startup()`; any `Error`-level message in non-`DEBUG` mode raises `ImproperlyConfigured`.
- **Engine created at import time** — `get_engine()` created the `AsyncEngine` when `buraq.core.db` was first imported, before user settings could be applied. Engine creation is now deferred via a `_LazyEngine` proxy until the first database operation.
- **`QuerySet.exists()` performance** — previously called `first()` which loaded a full model instance; now issues `SELECT 1 FROM (subquery) LIMIT 1`.
- **`has_perms()` doing N × 5 DB queries** — `has_perms(perms)` called `has_perm()` once per permission, each executing up to 5 queries. A `_get_all_permission_codenames()` helper now fetches all permissions in 3 queries; `has_perm`, `has_perms`, and `has_module_perms` all share the result.
- **`permission_required` async detection** — checked `inspect.iscoroutine(result)` after calling, which silently fell through when `has_perm` is not a coroutine function. Changed to `inspect.iscoroutinefunction(user.has_perm)` before calling.
- **`BaseFormSet.errors` list length mismatch** — `_errors` was shorter than `forms` when empty extra forms were skipped. Empty forms now append `{}` to keep the lists aligned.
- **`BaseFormSet.cleaned_data` was a method, not a property** — returned a bound method object instead of data. Changed to `@property`.
- **`asyncio.get_event_loop()` deprecated in Python 3.10+** — `FileSystemStorage` used the deprecated form inside async methods. Replaced with `asyncio.get_running_loop()`.
- **Private Starlette import in `RequestFactory`** — `_TestClientTransport` is an internal symbol that can be removed in any Starlette release. Import removed.
- **`asyncSetUp` failure leaked event loop** — if `asyncSetUp` raised, `TestCase.setUp` exited without closing the loop. Both methods now use `try/finally`.
- **Backend cache not used** — `_load_backends()` re-instantiated all auth backend classes on every `authenticate()` call. Result is now cached at module level.
- **`TruncHour/Day/Week/Month/Quarter/Year` were PostgreSQL-only** — all truncation functions used `func.date_trunc(...)`, which is a PostgreSQL extension. On SQLite the queries raised `OperationalError`; on MySQL/MariaDB they produced wrong results. All six functions now detect the configured database dialect via `DATABASE_URL` and emit `strftime` for SQLite, `date_format` for MySQL/MariaDB, and `date_trunc` for PostgreSQL.

### Changed

- **Password utilities relocated** — `hash_password()` and `verify_password()` moved from the now-deleted `buraq/core/auth.py` to `buraq/contrib/auth/_passwords.py`; all internal call sites updated; importing from `buraq.contrib.auth` (`make_password`, `check_password`) is unchanged
- **`buraq.core.auth` deleted** — the module contained only dead JWT helpers (`create_access_token`, `get_current_user_id`) and the password functions now in `_passwords.py`; no public import path existed
- **`buraq.core.middleware` deleted** — `security_headers_middleware` and `register_middleware` inlined directly into `buraq.core.application`; the separate module was an import-only indirection with no public API
- **`buraq.db.transaction` moved to `buraq.orm.transaction`** — transaction logic now lives under `orm/`; `buraq.db` re-exports `transaction`, `atomic`, and `on_commit` for backward compatibility
- **`buraq.views.decorators/` flattened** — the two-file directory (`__init__.py` + `csp.py`) replaced by a single `buraq/views/decorators.py`; public import paths unchanged
- **`LoginView`/`LogoutView` rewritten to session auth** — dead JWT functions `obtain_auth_token` and `get_me` (which referenced `create_access_token` and `get_current_user_id`, both removed in a prior cleanup) removed from `contrib/auth/views.py`; `LoginView.post()` now calls `authenticate()` then `login()` (session-based); `LogoutView.get()` now calls `logout()` instead of deleting a JWT cookie
- **`aiosqlite` moved to core dependencies** — the default `DATABASE_URL` uses `sqlite+aiosqlite://`; new projects failed immediately without it; `aiosqlite` is now bundled so SQLite works out of the box with no extra install
- **`asyncpg` moved to optional `[postgres]` extra** — PostgreSQL C extension is no longer pulled in for all users; install with `pip install "buraq[postgres]"` or `uv add "buraq[postgres]"`
- **`[production]` extra removed** — the extra listed `whitenoise` and `gunicorn`, neither of which is imported anywhere in the framework; `granian` (Rust ASGI server) has been bundled in core since 1.0.0 and serves production traffic without additional packages
- `path()` now accepts an optional dict as the third positional argument to pass extra keyword arguments to the view; internally applied via `functools.partial`

## [1.4.0] - 2026-08-04

### Added
- `buraq.utils.text` — string utilities: `slugify()`, `truncatechars()`, `truncatewords()`, `truncatechars_html()`, `truncatewords_html()`, `capfirst()`, `camel_case_to_spaces()`, `get_valid_filename()`, `smart_split()`, `wrap()`, `unescape_entities()`; zero extra dependencies
- `buraq.template.register` — decorator API for custom template globals, filters, and tests; `@register.global`, `@register.filter`, `@register.test`; supports `name=` and `is_safe=` options
- Auto-discovery of `templatetags.py` in every `INSTALLED_APPS` app at startup; no `{% load %}` required

## [1.3.0] - 2026-08-04

### Added
- `HttpResponse`, `JsonResponse`, `StreamingHttpResponse` — HTTP response classes; `JsonResponse` uses orjson (Rust) for high-performance serialization
- `Http404` — raise in any view to return a 404 response; exception handler registered automatically at app startup
- `HttpResponseRedirect`, `HttpResponsePermanentRedirect` — 302 and 301 redirects
- `HttpResponseNotFound`, `HttpResponseForbidden`, `HttpResponseBadRequest`, `HttpResponseNotAllowed`, `HttpResponseGone`, `HttpResponseNotModified`, `HttpResponseServerError` — standard HTTP error responses
- `buraq.utils.timezone` — timezone utilities: `now()`, `localtime()`, `localdate()`, `make_aware()`, `make_naive()`, `is_aware()`, `is_naive()`, `activate()`, `deactivate()`, `override()`; uses stdlib `zoneinfo` (C extension, zero extra deps), async-safe via `contextvars`
- `USE_TZ` and `TIME_ZONE` settings
- `url_has_allowed_host_and_scheme()` — open redirect protection via `buraq.utils.http`
- Sitemaps framework (`buraq.contrib.sitemaps`): `Sitemap`, `GenericSitemap`, async `sitemap` view; XML generated via stdlib ElementTree C accelerator
- `buraq.template.loader`: `render_to_string()`, `get_template()`, `select_template()`, `TemplateDoesNotExist`
- `render_to_string()` added to `buraq.shortcuts`
- `AuthenticationMiddleware` — reads `_auth_user_id` from session, fetches `User`, sets `request.user`; falls back to `AnonymousUser` for unauthenticated requests
- `AnonymousUser` — represents unauthenticated users; `is_authenticated = False`, `is_staff = False`, `is_superuser = False`
- `User.is_authenticated` — `True` on the `User` model so `request.user.is_authenticated` works uniformly
- `buraq.contrib.auth.authenticate(request, username, password)` — verifies credentials via Argon2, returns `User` or `None`
- `buraq.contrib.auth.login(request, user)` — writes `_auth_user_id` to session, cycles session key (session fixation protection), updates `last_login`
- `buraq.contrib.auth.logout(request)` — flushes session, resets `request.user` to `AnonymousUser`
- `@login_required`, `@staff_required`, `@superuser_required` now check `request.user.is_authenticated` / `.is_staff` / `.is_superuser` (session-based) instead of `Authorization: Bearer` tokens
- `@cache_control(**kwargs)` — set `Cache-Control` response headers declaratively (e.g. `max_age`, `public`, `no_store`)
- `@never_cache` — set headers to prevent any caching of a view's response
- `@vary_on_headers(*headers)` — add `Vary` header so caches key on specified request headers
- `@vary_on_cookie` — shortcut for `@vary_on_headers("Cookie")`
- `@cache_page(timeout)` — cache a full view response for N seconds; strips sensitive headers before storing
- `@require_http_methods(*methods)` — return 405 if request method is not in the allowed list
- `require_GET`, `require_POST`, `require_safe` — pre-built single-method restrictor decorators
- `TranslatableModel` and `TranslatedFields` (`buraq.contrib.i18n.models`) — per-language field translations stored in an auto-created `{table}_translation` companion table; Alembic detects the table automatically
- `await model.get_translation(lang_code)` — fetch translation row; raises `DoesNotExist` if missing
- `await model.safe_translation_getter(field, language_code, fallback_language, default)` — fetch a translated field value, never raises
- `await model.set_translation(lang_code, **fields)` — upsert a translation row
- `await model.get_translations()` — list all translation rows for an instance
- `await model.delete_translation(lang_code)` — remove one translation row

## [1.2.0] - 2026-08-03

### Added
- `i18n_patterns()` — marks URL groups as language-prefixed for automatic URL generation
- `reverse("name", **kwargs)` — global URL reversal, no request needed; auto-prepends active language prefix for i18n routes
- `translate_url(url, lang)` — rewrites any URL path to a different language prefix
- `set_language` view — POST/GET endpoint that redirects to the language-prefixed URL (`/i18n/set_language?language=ar&next=/about` → `/ar/about`)
- `LocaleMiddleware` now strips the language prefix from the path before routing (`/ar/about` → router sees `/about`)
- `ngettext_lazy()`, `pgettext_lazy()`, `npgettext_lazy()` — lazy translation variants for use in model/form class bodies
- `npgettext()` — immediate context-disambiguated pluralization
- `deactivate_all()` — disables translation for the current async context; all calls return the original string
- `check_for_language(lang)` — returns `True` if the language is in `LANGUAGES`
- `to_locale("en-us")` — converts a language code to locale format (`"en_US"`)
- `get_language_bidi()` — returns `True` for right-to-left languages (Arabic, Hebrew, Persian, Urdu, and others)
- `override(language)` context manager — temporarily activates a language; works in sync and async code
- `get_language_switch_urls(request)` — returns per-language URLs for the current page
- `warmup_catalogs()` — pre-loads all `.mo` catalogs; called automatically at app startup when `USE_I18N = True`
- Jinja2 globals: `_`, `gettext`, `ngettext`, `pgettext`, `get_language`, `get_language_bidi` auto-registered when `USE_I18N = True` — no need to pass from every view

## [1.1.0] - 2026-08-02

### Added
- Internationalization (i18n) support via `buraq.utils.translation`
- `gettext`, `gettext_lazy`, `ngettext`, `pgettext` translation functions
- `LocaleMiddleware` — detects active language from URL prefix, cookie, or `Accept-Language` header
- `buraq makemessages` command — extracts translatable strings into `.po` files via Babel
- `buraq compilemessages` command — compiles `.po` files into binary `.mo` files
- i18n settings: `USE_I18N`, `LANGUAGE_CODE`, `LANGUAGES`, `LOCALE_PATHS`, `LANGUAGE_COOKIE_NAME`
- Babel added as a core dependency for message extraction and locale data

## [1.0.0] - 2026-07-31

### Added
- Async-first ORM built on SQLAlchemy 2.0
- Alembic-based migrations with `buraq makemigrations` and `buraq migrate` commands
- Function-based and class-based views with async support
- `path()` URL routing with type-safe converters
- Jinja2 template engine
- ModelForm and Form classes with field-level validation
- Built-in authentication system with JWT (PyJWT) and session support
- Flash messages backed by session storage
- Middleware system compatible with ASGI
- Built-in admin panel at `/admin` (replaced by the full `BuraqAdmin` in `[Unreleased]`)
- Session management with Redis and cookie backends
- Cache framework with Redis and Memcached backends
- Signals system for decoupled application components
- Static file serving with WhiteNoise
- Email sending via aiosmtplib
- Rate limiting via SlowAPI
- Security headers via the `secure` package
- Management CLI (`buraq runserver`, `buraq shell`, `buraq createsuperuser`)
- Granian (Rust ASGI server) with uvicorn fallback
- Argon2 password hashing via argon2-cffi
- orjson for high-performance JSON serialization

[Unreleased]: https://github.com/nezanuha/buraq/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/nezanuha/buraq/compare/v1.5.2...v1.6.0
[1.5.2]: https://github.com/nezanuha/buraq/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/nezanuha/buraq/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/nezanuha/buraq/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/nezanuha/buraq/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/nezanuha/buraq/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/nezanuha/buraq/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nezanuha/buraq/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nezanuha/buraq/releases/tag/v1.0.0