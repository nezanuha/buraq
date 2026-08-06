# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

**ORM — Expressions & Functions**
- `buraq.orm.expressions` — `Case`, `When`, `Value`, `OuterRef`, `Subquery`, `Exists`, `ExpressionWrapper` for conditional queries and correlated subqueries
- `buraq.orm.functions` — 60+ database functions: date/time (`Now`, `TruncDate`, `TruncMonth`, `TruncYear`, `ExtractYear`, …), string (`Concat`, `Upper`, `Lower`, `Trim`, `Replace`, `Substr`, `LPad`, …), math (`Abs`, `Ceil`, `Floor`, `Round`, `Sqrt`, `Power`, …), NULL handling (`Coalesce`, `NullIf`, `Greatest`, `Least`), type casting (`Cast`), hash (`MD5`, `SHA1`, `SHA256`, `SHA512`)
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

**CSRF**
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
- `buraq.contrib.postgres.search` — `SearchQuery`, `SearchVector`, `SearchRank`; all use `plainto_tsquery` for safe user input
- `buraq.contrib.postgres.aggregates` — `ArrayAgg`, `StringAgg`, `JsonAgg`, `BitAnd`, `BitOr`
- `buraq.contrib.postgres.functions` — `Unaccent`, `Now`, `Random`

**Testing**
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
- `buraq.serializers` — serialize querysets and model instances to JSON, Python, or XML; JSON backend uses `orjson` with stdlib fallback

**Settings**
- `AUTH_PASSWORD_VALIDATORS` — pre-configured with `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`

**Management commands**
- `listurls` — prints a table of all registered routes with path, HTTP methods, and route name; accepts `--app module:obj`

**Cache**
- Redis `get_many` / `set_many` optimised — `get_many()` uses a single `MGET` command; `set_many()` uses a pipeline (previously one round-trip per key)

### Fixed

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

### Changed

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
- Admin interface powered by SQLAdmin
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

[Unreleased]: https://github.com/nezanuha/buraq/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/nezanuha/buraq/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/nezanuha/buraq/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/nezanuha/buraq/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nezanuha/buraq/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nezanuha/buraq/releases/tag/v1.0.0