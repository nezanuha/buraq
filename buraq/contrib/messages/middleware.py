"""Message middleware.

Lives with the messages app rather than in core middleware, because that is what
it belongs to -- the same split the framework this borrows from uses. Buraq's
messages are written straight to the session, so a project needs this only for
parity with code that expects it to be in the stack.
"""

class MessageMiddleware:
    """
    Middleware placeholder for flash messages.

    The actual message storage is handled by ``buraq.contrib.messages`` via
    the session; this middleware is provided for compatibility in
    ``MIDDLEWARE`` lists.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


__all__ = ["MessageMiddleware"]
