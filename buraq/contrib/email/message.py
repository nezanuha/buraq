from dataclasses import dataclass, field
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from buraq.conf import settings


@dataclass
class EmailMessage:
    subject: str
    body: str
    to: list[str]
    from_email: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: list[str] = field(default_factory=list)
    attachments: list[tuple[str, bytes, str]] = field(default_factory=list)
    content_type: str = "plain"

    def _get_from(self) -> str:
        return self.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")  # type: ignore[attr-defined]

    def attach(
        self, filename: str, content: bytes, mimetype: str = "application/octet-stream"
    ) -> None:
        self.attachments.append((filename, content, mimetype))

    def attach_file(self, path: str) -> None:
        p = Path(path)
        self.attach(p.name, p.read_bytes())

    def build_mime(self) -> MIMEMultipart:
        msg = MIMEMultipart("alternative" if self.content_type == "html" else "mixed")
        msg["Subject"] = self.subject
        msg["From"] = self._get_from()
        msg["To"] = ", ".join(self.to)
        if self.cc:
            msg["Cc"] = ", ".join(self.cc)
        if self.reply_to:
            msg["Reply-To"] = ", ".join(self.reply_to)

        msg.attach(MIMEText(self.body, self.content_type))

        for filename, content, mimetype in self.attachments:
            main, sub = mimetype.split("/", 1)
            part = MIMEBase(main, sub)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

        return msg

    async def send(self) -> bool:
        from buraq.contrib.email.send import get_connection
        backend = get_connection()
        return await backend.send(self)


@dataclass
class EmailMultiAlternatives(EmailMessage):
    """Email with both plain text and HTML alternatives."""
    html_body: str = ""

    def build_mime(self) -> MIMEMultipart:
        if self.attachments:
            # mixed outer wrapping alternative inner — so attachments work alongside HTML
            outer = MIMEMultipart("mixed")
            outer["Subject"] = self.subject
            outer["From"] = self._get_from()
            outer["To"] = ", ".join(self.to)
            if self.cc:
                outer["Cc"] = ", ".join(self.cc)
            if self.reply_to:
                outer["Reply-To"] = ", ".join(self.reply_to)
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(self.body, "plain"))
            if self.html_body:
                alt.attach(MIMEText(self.html_body, "html"))
            outer.attach(alt)
            for filename, content, mimetype in self.attachments:
                main, sub = mimetype.split("/", 1)
                part = MIMEBase(main, sub)
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                outer.attach(part)
            return outer

        msg = MIMEMultipart("alternative")
        msg["Subject"] = self.subject
        msg["From"] = self._get_from()
        msg["To"] = ", ".join(self.to)
        if self.cc:
            msg["Cc"] = ", ".join(self.cc)
        if self.reply_to:
            msg["Reply-To"] = ", ".join(self.reply_to)
        msg.attach(MIMEText(self.body, "plain"))
        if self.html_body:
            msg.attach(MIMEText(self.html_body, "html"))
        return msg
