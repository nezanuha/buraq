import importlib

from buraq.conf import settings
from buraq.contrib.email.backends.base import BaseEmailBackend
from buraq.contrib.email.message import EmailMessage, EmailMultiAlternatives

_backends: dict[str | None, BaseEmailBackend] = {}


def _load_backend(backend_path: str, **kwargs) -> BaseEmailBackend:
    module_path, class_name = backend_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs) if kwargs else cls()


def get_connection(using: str | None = None) -> BaseEmailBackend:
    """
    Return an email backend instance.

    - ``using=None`` — uses the legacy ``EMAIL_BACKEND`` setting (default).
    - ``using="name"`` — looks up the named entry in the ``MAILERS`` dict.

    Backends are cached per connection name after first instantiation.

    Usage::

        conn = get_connection(using="transactional")
        await conn.send(message)
    """
    cache_key = using

    if cache_key not in _backends:
        mailers: dict = getattr(settings, "MAILERS", {})

        if using is not None:
            if using not in mailers:
                raise ValueError(
                    f"No mailer named {using!r} in MAILERS setting. "
                    f"Available: {list(mailers)}"
                )
            config = dict(mailers[using])
            backend_path = config.pop("BACKEND")
            _backends[cache_key] = _load_backend(backend_path, **config)
        else:
            # Fall back to the single EMAIL_BACKEND setting
            backend_path = getattr(
                settings,
                "EMAIL_BACKEND",
                "buraq.contrib.email.backends.console.ConsoleEmailBackend"
                if settings.DEBUG
                else "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
            )
            _backends[cache_key] = _load_backend(backend_path)

    return _backends[cache_key]


async def send_mail(
    subject: str,
    message: str,
    recipient_list: list[str],
    from_email: str | None = None,
    html_message: str | None = None,
    using: str | None = None,
) -> bool:
    """
    Send an email.

    ``using`` selects a named mailer from the ``MAILERS`` setting.
    Omit (or pass ``None``) to use the default ``EMAIL_BACKEND``.
    """
    if html_message:
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            to=recipient_list,
            from_email=from_email,
            html_body=html_message,
        )
    else:
        email = EmailMessage(
            subject=subject,
            body=message,
            to=recipient_list,
            from_email=from_email,
        )
    return await get_connection(using).send(email)


async def send_mass_mail(
    messages: list[tuple[str, str, list[str]]],
    using: str | None = None,
) -> int:
    """Send multiple emails. Each tuple: (subject, body, recipient_list)"""
    emails = [
        EmailMessage(subject=subject, body=body, to=recipients)
        for subject, body, recipients in messages
    ]
    return await get_connection(using).send_many(emails)


async def mail_admins(
    subject: str,
    message: str,
    html_message: str | None = None,
    using: str | None = None,
) -> bool:
    """Send an email to all ADMINS defined in settings."""
    admins = getattr(settings, "ADMINS", [])
    if not admins:
        return False
    if isinstance(admins[0], (list, tuple)):
        recipients = [email for _, email in admins]
    else:
        recipients = list(admins)
    return await send_mail(subject, message, recipients, html_message=html_message, using=using)


async def mail_managers(
    subject: str,
    message: str,
    html_message: str | None = None,
    using: str | None = None,
) -> bool:
    """Send an email to all MANAGERS defined in settings."""
    managers = getattr(settings, "MANAGERS", [])
    if not managers:
        return False
    if isinstance(managers[0], (list, tuple)):
        recipients = [email for _, email in managers]
    else:
        recipients = list(managers)
    return await send_mail(subject, message, recipients, html_message=html_message, using=using)


async def send_template_mail(
    subject: str,
    template_name: str,
    context: dict,
    recipient_list: list[str],
    from_email: str | None = None,
    using: str | None = None,
) -> bool:
    """Send an email rendered from a Jinja2 template."""
    from buraq.core.templating import get_templates
    templates = get_templates()
    html_body = templates.get_template(template_name).render(context)

    import re
    plain_body = re.sub(r"<[^>]+>", "", html_body).strip()

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        to=recipient_list,
        from_email=from_email,
        html_body=html_body,
    )
    return await get_connection(using).send(email)
