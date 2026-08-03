# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/nezanuha/buraq/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/nezanuha/buraq/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nezanuha/buraq/releases/tag/v1.0.0
