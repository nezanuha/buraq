"""
Cookie-based signed sessions.

Usage:
    # config/urls.py
    from buraq.contrib.sessions import SessionMiddleware
    from buraq.conf import settings

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    # In any view:
    request.session["cart"] = [1, 2, 3]
    cart = request.session.get("cart", [])
    request.session.flush()   # clear session
"""
from buraq.contrib.sessions.middleware import SessionMiddleware

__all__ = ["SessionMiddleware"]
