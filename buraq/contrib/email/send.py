import importlib

from buraq.conf import settings
from buraq.contrib.email.backends.base import BaseEmailBackend
from buraq.contrib.email.message import EmailMessage, EmailMultiAlternatives

_backend: BaseEmailBackend | None = None


def get_backend() -> BaseEmailBackend:
    global _backend
    if _backend is None:
        backend_path = getattr(
            settings,
            "EMAIL_BACKEND",  # type: ignore[attr-defined]
            "buraq.contrib.email.backends.console.ConsoleEmailBackend"
            if settings.DEBUG
            else "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
        )
        module_path, class_name = backend_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        _backend = getattr(module, class_name)()
    return _backend


async def send_mail(
    subject: str,
    message: str,
    recipient_list: list[str],
    from_email: str | None = None,
    html_message: str | None = None,
) -> bool:
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
    return await get_backend().send(email)


async def send_mass_mail(messages: list[tuple[str, str, list[str]]]) -> int:
    """Send multiple emails. Each tuple: (subject, body, recipient_list)"""
    emails = [
        EmailMessage(subject=subject, body=body, to=recipients)
        for subject, body, recipients in messages
    ]
    return await get_backend().send_many(emails)


async def send_template_mail(
    subject: str,
    template_name: str,
    context: dict,
    recipient_list: list[str],
    from_email: str | None = None,
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
    return await get_backend().send(email)
