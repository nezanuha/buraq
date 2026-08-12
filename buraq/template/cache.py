"""
{% cache %} template tag for Buraq/Jinja2.

Caches the rendered content of a template block using the configured cache backend.

Usage::

    {% cache 300 "sidebar" %}
        <expensive content here>
    {% endcache %}

    {# Dynamic key: #}
    {% cache 3600 "user-profile-" ~ user.id %}
        <user-specific content>
    {% endcache %}

    {# Disable caching (timeout=0): #}
    {% cache 0 "uncached" %}
        <never cached>
    {% endcache %}

The timeout is in seconds. A timeout of 0 skips both the cache read and write.
"""
from jinja2 import nodes
from jinja2.ext import Extension


class CacheExtension(Extension):
    tags = {"cache"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        timeout = parser.parse_expression()
        cache_key = parser.parse_expression()
        body = parser.parse_statements(["name:endcache"], drop_needle=True)
        return nodes.CallBlock(
            self.call_method("_cache_support", [timeout, cache_key]),
            [], [], body,
        ).set_lineno(lineno)

    def _cache_support(self, timeout, cache_key, caller):
        if not timeout:
            return caller()
        from buraq.contrib.cache.core import _get_backend
        backend = _get_backend()
        cached = backend.get_sync(cache_key)
        if cached is not None:
            return cached
        content = caller()
        backend.set_sync(cache_key, content, timeout)
        return content
