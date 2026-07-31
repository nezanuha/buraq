from dataclasses import dataclass

DEBUG   = 10
INFO    = 20
SUCCESS = 25
WARNING = 30
ERROR   = 40

LEVEL_TAGS = {
    DEBUG:   "debug",
    INFO:    "info",
    SUCCESS: "success",
    WARNING: "warning",
    ERROR:   "error",
}


@dataclass
class Message:
    level: int
    message: str
    extra_tags: str = ""

    @property
    def tags(self) -> str:
        level_tag = LEVEL_TAGS.get(self.level, "")
        parts = [t for t in (level_tag, self.extra_tags) if t]
        return " ".join(parts)

    @property
    def level_tag(self) -> str:
        return LEVEL_TAGS.get(self.level, "")

    def __str__(self) -> str:
        return self.message


class MessageStorage:
    def __init__(self):
        self._messages: list[Message] = []
        self.used = False

    def add(self, level: int, message: str, extra_tags: str = "") -> None:
        self._messages.append(Message(level=level, message=message, extra_tags=extra_tags))

    def get_and_clear(self) -> list[Message]:
        msgs = list(self._messages)
        self._messages.clear()
        self.used = True
        return msgs

    def __iter__(self):
        self.used = True
        return iter(self._messages)

    def __len__(self):
        return len(self._messages)

    def __contains__(self, item):
        return item in self._messages
