# Email

## Configuration

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
