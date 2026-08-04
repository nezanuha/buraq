# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/nezanuha/buraq/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/nezanuha/buraq/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/nezanuha/buraq/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nezanuha/buraq/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nezanuha/buraq/releases/tag/v1.0.0
