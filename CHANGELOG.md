# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

**ORM — QuerySet**
- `Q.__xor__` — XOR set operation on Q objects (emulated as `(A OR B) AND NOT (A AND B)` for full database compatibility)

**Security Middleware**
- `buraq.middleware.SecurityMiddleware` — ASGI middleware that injects security headers on every response: `Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Permissions-Policy`; optional HTTP→HTTPS redirect via `SECURE_SSL_REDIRECT`
- New settings: `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`, `SECURE_SSL_REDIRECT`, `SECURE_PERMISSIONS_POLICY`, `X_FRAME_OPTIONS`

**Forms**
- `RadioSelect` widget — renders radio button list, one per choice
- `CheckboxSelectMultiple` widget — renders checkbox list, multiple selections
- `MultipleHiddenInput` widget — renders multiple hidden inputs for list values (used by formsets)

**Utilities**
- `buraq.utils.choices` — `TextChoices` and `IntegerChoices` enum base classes with `.choices`, `.labels`, `.values`, `.names` class properties; use for `CharField`/`IntegerField` choice definitions
- `buraq.utils.feedgenerator` — `Rss201rev2Feed` (RSS 2.0.1) and `Atom1Feed` (Atom 1.0) feed generators; pure stdlib, no external dependencies; `add_item()`, `writeString()`, `latest_post_date()`

**Serialization**
- `buraq.serializers` — serialize querysets and model instances to JSON, Python, or XML via `serialize(format, queryset)` / `deserialize(format, data)`; JSON backend uses `orjson` (Rust-based, 2–10× faster than stdlib) with automatic stdlib fallback; XML via `xml.etree.ElementTree`

**PostgreSQL**
- `buraq.contrib.postgres.fields` — `JSONField` (JSONB), `ArrayField` (ARRAY), `HStoreField` (hstore) column types for SQLAlchemy models
- `buraq.contrib.postgres.search` — `SearchQuery` (full-text WHERE clause), `SearchVector` (multi-field tsvector), `SearchRank` (ts_rank annotation expression); all use `plainto_tsquery` for safe user input
- `buraq.contrib.postgres.aggregates` — `ArrayAgg`, `StringAgg`, `JsonAgg`, `BitAnd`, `BitOr` aggregate functions for use with `aggregate()` / `annotate()`
- `buraq.contrib.postgres.functions` — `Unaccent`, `Now`, `Random` SQL function helpers

**System Checks**
- `buraq.checks` — startup validation framework: `@register` decorator, `run_checks()`, message classes `Debug` / `Info` / `Warning` / `Error` / `Critical`
- Built-in checks: `SECRET_KEY` strength (`security.E001`, `security.W001`), `DEBUG + ALLOWED_HOSTS` safety (`security.W002`), SQLite in production (`database.W001`)

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
- `buraq.contrib.redirects.middleware.RedirectFallbackMiddleware` — intercepts 404 responses and checks the `Redirect` table before giving up

**Sites**
- `buraq.contrib.sites.models.Site` — multi-domain support; `Site.get_current(request)` resolves the current domain from the Host header

**App Registry**
- `buraq.apps.AppConfig` — base class for application configuration with `name`, `verbose_name`, `label`, `async ready()` hook
- `buraq.apps.apps` — global `Apps` registry; `populate(INSTALLED_APPS)`, `run_ready_hooks()`, `get_app_config(label)`, `is_installed(app_name)`

### Fixed
- **`QuerySet.exists()` performance** — previously called `first()` which loaded a full model instance; now issues `SELECT 1 FROM (subquery) LIMIT 1` — no object hydration, minimal I/O

### Added

**ORM — Expressions & Functions**
- `buraq.orm.expressions` — `Case`, `When`, `Value`, `OuterRef`, `Subquery`, `Exists`, `ExpressionWrapper` for conditional queries and correlated subqueries
- `buraq.orm.functions` — 60+ database functions: date/time (`Now`, `TruncDate`, `TruncMonth`, `TruncYear`, `ExtractYear`, …), string (`Concat`, `Upper`, `Lower`, `Trim`, `Replace`, `Substr`, `LPad`, …), math (`Abs`, `Ceil`, `Floor`, `Round`, `Sqrt`, `Power`, …), NULL handling (`Coalesce`, `NullIf`, `Greatest`, `Least`), type casting (`Cast`), hash (`MD5`, `SHA1`, `SHA256`, `SHA512`)
- `buraq.orm.window` — window function support: `Window`, `RowNumber`, `Rank`, `DenseRank`, `PercentRank`, `CumeDist`, `Ntile`, `Lag`, `Lead`, `FirstValue`, `LastValue`, `NthValue`

**ORM — QuerySet**
- `QuerySet.select_for_update(nowait, skip_locked)` — `SELECT … FOR UPDATE` row-level locking
- `QuerySet.earliest(*fields)` / `.latest(*fields)` — first/last object by field
- `QuerySet.dates(field, kind)` / `.datetimes(field, kind)` — distinct date/datetime values
- `QuerySet.raw(sql, params)` — raw SQL with named parameters, returns list of dicts

**ORM — Fields**
- `PositiveBigIntegerField` — big integer with `>= 0` constraint
- `DurationField` — maps Python `timedelta` to database `INTERVAL`
- `GenericIPAddressField` — IPv4/IPv6 with `protocol` option

**Auth**
- `Permission`, `Group`, `UserGroup`, `UserPermission`, `GroupPermission` models (`buraq.contrib.auth.models`)
- `User.has_perm(perm)`, `User.has_perms(perms)`, `User.has_module_perms(app)` — async permission checks
- `User.groups()`, `User.user_permissions()` — async relation accessors
- `make_password()`, `check_password()`, `validate_password()`, `update_session_auth_hash()` — password utilities (`buraq.contrib.auth`)

**Views**
- `FormView` — generic class-based view for displaying and processing a single form
- `LoginRequiredMixin`, `PermissionRequiredMixin`, `UserPassesTestMixin`, `AccessMixin` — auth mixins for class-based views (`buraq.views.mixins`)
- `@user_passes_test(fn)` — decorator that calls `fn(user)` and redirects on failure
- `@cache_page(timeout)` — full-response cache decorator; uses active cache backend

**CSRF**
- `buraq.contrib.csrf` — `get_token(request)`, `@csrf_protect`, `@ensure_csrf_cookie`

**Forms**
- `ModelChoiceField` — single model instance picker from a queryset
- `ModelMultipleChoiceField` — multi-select model picker with `fetch_many()`
- `TypedMultipleChoiceField` — `MultipleChoiceField` with type coercion

**Views — Archive**
- `WeekArchiveView` — list objects for a given ISO week number
- `DayArchiveView` — list objects for a specific calendar day
- `TodayArchiveView` — list objects for today's date (no URL params needed)
- `ArchiveIndexView` — top-level archive listing all distinct years
- `DateDetailView` — retrieve a single object by year/month/day + pk or slug

**Email**
- `mail_admins(subject, message)` — send email to all `ADMINS` in settings
- `mail_managers(subject, message)` — send email to all `MANAGERS` in settings

**Validators**
- `BaseValidator` — base class for limit-based validators
- `StepValueValidator` — validate that a value is a multiple of a given step
- `validate_integer()`, `validate_ipv4_address()`, `validate_ipv6_address()`, `validate_ipv46_address()`
- `validate_image_file_extension()` — validate uploaded image file types
- `FileExtensionValidator(allowed_extensions)` — validate arbitrary file extensions
- `int_list_validator(sep, allow_negative)` — validate comma-separated integer strings

**Utilities**
- `buraq.utils.html` — `SafeString`, `mark_safe`, `escape`, `escapejs`, `conditional_escape`, `format_html`, `format_html_join`, `linebreaks`, `strip_tags`, `urlize`
- `buraq.utils.encoding` — `force_str`, `smart_str`, `force_bytes`, `iri_to_uri`, `uri_to_iri`, `escape_uri_path`
- `buraq.utils.crypto` — `get_random_string`, `constant_time_compare`, `pbkdf2`, `salted_hmac`
- `buraq.utils.functional` — `cached_property`, `LazyObject`, `SimpleLazyObject`, `lazy`, `classproperty`
- `buraq.utils.dateparse` — `parse_date`, `parse_time`, `parse_datetime`, `parse_duration` — ISO 8601 + `DD HH:MM:SS` formats, no external dependencies

**Humanize**
- `buraq.contrib.humanize` — `intcomma`, `ordinal`, `apnumber`, `pluralize`, `naturalday`, `naturaltime`, `naturalduration`, `intword`

**Formsets**
- `buraq.forms.formsets` — `BaseFormSet`, `BaseModelFormSet`, `BaseInlineFormSet`
- `formset_factory(form, extra, can_delete, min_num, max_num, validate_min, validate_max)` — create a FormSet class from any `Form`
- `modelformset_factory(model, fields, extra, …)` — create a ModelFormSet; auto-generates a `ModelForm` if none provided
- `inlineformset_factory(parent, child, fk_field, …)` — create an InlineFormSet that stamps the parent FK on save; FK auto-detected from foreign keys if `fk_field` is omitted
- `BaseFormSet.cleaned_data` — property returning list of non-empty valid form dicts
- `BaseFormSet.management_form_html()` — renders the four hidden management inputs

**File Storage**
- `buraq.core.files` — `File`, `ContentFile`, `UploadedFile` wrappers
- `FileSystemStorage(location, base_url)` — async `save`, `open`, `delete`, `exists`, `size`, `listdir`; safe path traversal; auto-suffixes on name collision
- `default_storage` — lazy proxy to configured `DEFAULT_FILE_STORAGE` backend
- `UploadedFile.from_starlette(upload)` — build from Starlette `UploadFile`

**Testing**
- `buraq.test.AsyncClient` — exercises the full ASGI stack in-process; `get`, `post`, `put`, `patch`, `delete`, `head`, `options`; `json=` shorthand; `headers=` injection; `follow_redirects=`; `force_login(user)`
- `buraq.test.RequestFactory` — builds `starlette.requests.Request` objects for unit-testing individual views
- `buraq.test.TestCase` — async-aware `unittest.TestCase` with `asyncSetUp`/`asyncTearDown`; assertion helpers: `assertContains`, `assertNotContains`, `assertRedirects`, `assertStatusCode`, `assertJSONEqual`
- `buraq.test.SimpleTestCase` — assertion helpers without database or client
- `buraq.test.TransactionTestCase` — same as `TestCase`, documented for transaction-isolated tests

**Auth — Multiple Backends**
- `buraq.contrib.auth.backends.ModelBackend` — default username/password backend
- `AUTHENTICATION_BACKENDS` setting (default: `["buraq.contrib.auth.backends.ModelBackend"]`)
- `authenticate()` now iterates all configured backends; stamps `user._auth_backend` with the winning backend path
- `_clear_backend_cache()` — utility to invalidate the cached backend list at runtime

**ORM — Deferred Loading (fixed)**
- `QuerySet.defer(*fields)` — now uses SQLAlchemy `defer()` option; returns proper ORM instances with deferred columns loaded on access
- `QuerySet.only(*fields)` — now uses `load_only()` option; returns proper ORM instances

### Security

- **Event-loop blocking on password hashing** — `make_password()` and `check_password()` called Argon2 synchronously, blocking the event loop for ~100 ms on every hash/verify and stalling all concurrent requests. Both are now `async` and run via `asyncio.to_thread()`. `ModelBackend.authenticate()` received the same fix.
- **Username enumeration via timing** — `ModelBackend` returned instantly when a username did not exist but waited ~100 ms for Argon2 when the password was wrong. An attacker could enumerate valid usernames by measuring response time. A dummy Argon2 verify is now run for missing users so all code paths take the same time.
- **Session cookie served from page cache** — `@cache_page` stored the full response header dict, including `Set-Cookie`. A cached response was then served to other users with the original user's session cookie embedded. `set-cookie`, `authorization`, and `www-authenticate` headers are now stripped before the response is stored in cache.
- **Broken redirect URL on login** — `@login_required` embedded the raw current URL as the `next` query parameter without encoding it. A URL containing `?`, `&`, or `=` would corrupt the redirect query string. The value is now encoded with `urllib.parse.urlencode`.
- **SHA-1 as default in `salted_hmac`** — SHA-1 has been cryptographically broken since 2005. The default `algorithm` argument was `"sha1"`; it is now `"sha256"`.
- **Unbounded language code in `set_language` view** — a caller could POST an arbitrarily long string as the `language` parameter. Any downstream code that cached or logged it without a length guard could be exploited for memory exhaustion. The view now rejects any language code longer than 500 characters before calling `check_for_language`.

### Fixed

- **`has_perms()` doing N × 5 DB queries** — `has_perms(perms)` called `has_perm()` once per permission, and each `has_perm()` executed up to 5 sequential queries. For 10 permissions that was 50 queries per request. A new `_get_all_permission_codenames()` helper fetches all direct and group permissions in 3 queries; `has_perm`, `has_perms`, and `has_module_perms` all share this result. `has_perms(n)` is now always 3 queries regardless of how many permissions are checked.
- **`permission_required` async detection** — the decorator called `user.has_perm(perm)` then checked `inspect.iscoroutine(result)` after the fact. If the method is not a coroutine function the coroutine is never created and the check silently falls through. Changed to `inspect.iscoroutinefunction(user.has_perm)` before calling.
- **`BaseFormSet.errors` list length mismatch** — when empty extra forms were skipped during validation, the `_errors` list was shorter than `forms`. Iterating `zip(formset.forms, formset.errors)` would silently misalign form/error pairs. Empty forms now append `{}` to keep the lists the same length.
- **`BaseFormSet.cleaned_data` was a method, not a property** — `formset.cleaned_data` returned a bound method object instead of data. Changed to `@property`.
- **`defer()` and `only()` were no-ops** — `defer()` returned `self` unchanged; `only()` selected raw columns breaking ORM instance return. Both now use SQLAlchemy `defer()` / `load_only()` options and return proper model instances.
- **`asyncio.get_event_loop()` deprecated in Python 3.10+** — `FileSystemStorage` used the deprecated form inside async methods. Replaced with `asyncio.get_running_loop()`.
- **Private Starlette import in `RequestFactory`** — `_TestClientTransport` is an internal symbol that can be removed in any Starlette release. Import removed.
- **`asyncSetUp` failure leaked event loop** — if `asyncSetUp` raised, `TestCase.setUp` exited without closing the loop. `tearDown` then ran against a partially-initialised loop. Both methods now use `try/finally`.
- **Backend cache not used** — `_load_backends()` re-imported and re-instantiated all auth backend classes on every `authenticate()` call. Result is now cached at module level with a `_clear_backend_cache()` escape hatch.

### Changed
- `path()` now accepts an optional dict as the third positional argument to pass extra keyword arguments to the view (e.g. `path('/url', view, {'key': 'val'}, name='name')`); internally applied via `functools.partial`

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