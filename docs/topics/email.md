# Email

## Single backend (EMAIL_BACKEND)

Configure one global backend in settings:

```python title="config/settings.py"
# SMTP (production)
EMAIL_BACKEND       = "buraq.contrib.email.backends.smtp.SMTPEmailBackend"
EMAIL_HOST          = "smtp.gmail.com"
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = "you@gmail.com"
EMAIL_HOST_PASSWORD = "your-app-password"
DEFAULT_FROM_EMAIL  = "you@gmail.com"

# File backend (development — writes emails to disk)
EMAIL_BACKEND   = "buraq.contrib.email.backends.file.FileEmailBackend"
EMAIL_FILE_PATH = "./sent_emails"
```

## Multiple Mailers

Use `MAILERS` when you need distinct delivery channels — e.g. a transactional SMTP relay for account emails and a bulk relay for newsletters:

```python title="config/settings.py"
MAILERS = {
    "default": {
        "BACKEND":       "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
        "HOST":          "smtp.example.com",
        "PORT":          587,
        "HOST_USER":     "noreply@example.com",
        "HOST_PASSWORD": "secret",
        "USE_TLS":       True,
    },
    "bulk": {
        "BACKEND":       "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
        "HOST":          "bulk.relay.com",
        "PORT":          587,
        "HOST_USER":     "bulk@example.com",
        "HOST_PASSWORD": "secret",
        "USE_TLS":       True,
    },
}
```

Select a mailer with the `using=` argument on any send function:

```python
await send_mail("Welcome!", "Thanks for signing up.", ["user@example.com"], using="default")
await send_mail("Newsletter", body, recipients, using="bulk")
```

`using=None` (the default) falls back to the legacy `EMAIL_BACKEND` setting.

### get_connection()

Retrieve a backend instance directly:

```python
from buraq.contrib.email import get_connection

conn = get_connection(using="bulk")
await conn.send(message)
```

Backends are cached after the first call — no new connections on repeated calls.

### Custom backend

```python
from buraq.contrib.email.backends.base import BaseEmailBackend

class MyBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        self.api_key = kwargs.get("API_KEY")

    async def send(self, message) -> bool:
        return True  # call your API
```

Register in `MAILERS`:

```python
MAILERS = {
    "custom": {
        "BACKEND": "myapp.backends.MyBackend",
        "API_KEY": "sk-...",
    },
}
```

## Sending email

```python
from buraq.contrib.email import send_mail


await send_mail(
    subject    = "Welcome to Buraq Blog!",
    message    = "Thanks for signing up.",
    from_email = "noreply@myblog.com",
    to         = ["alice@example.com"],
)
```

## HTML email

```python
await send_mail(
    subject    = "Your post was published",
    message    = "Your post is now live.",   # plain text fallback
    html_message = "<h1>Your post is live!</h1><p>Visit it at <a href='...'>here</a>.</p>",
    from_email = "noreply@myblog.com",
    to         = ["alice@example.com"],
)
```

## Multiple recipients

```python
await send_mail(
    subject = "Newsletter",
    message = "This month's updates...",
    to      = ["alice@example.com", "bob@example.com"],
    cc      = ["editor@myblog.com"],
    bcc     = ["archive@myblog.com"],
)
```

## Send mass mail

Send many emails efficiently in a single backend call.

```python
from buraq.contrib.email import send_mass_mail

messages = [
    ("Welcome!", "Thanks for joining.", ["alice@example.com"]),
    ("Welcome!", "Thanks for joining.", ["bob@example.com"]),
]
count = await send_mass_mail(messages)   # → number of emails sent
```

## Mail admins / managers

Quickly notify your site administrators or managers. Configure the recipients in settings:

```python title="config/settings.py"
ADMINS   = [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
MANAGERS = [("Carol", "carol@example.com")]
```

```python
from buraq.contrib.email import mail_admins, mail_managers

# Notify all ADMINS
await mail_admins("Server error", "Traceback:\n...")

# Notify all MANAGERS
await mail_managers("New signup", "User alice@example.com just registered.")

# With HTML body
await mail_admins("Alert", "Plain text.", html_message="<b>Alert</b>")
```
