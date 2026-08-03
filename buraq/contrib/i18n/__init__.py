from buraq.contrib.i18n.middleware import LocaleMiddleware
from buraq.contrib.i18n.views import set_language
from buraq.urls import i18n_patterns, reverse
from buraq.utils.translation import (
    activate,
    check_for_language,
    deactivate,
    deactivate_all,
    get_language,
    get_language_bidi,
    get_language_info_list,
    get_language_switch_urls,
    get_supported_languages,
    gettext,
    gettext_lazy,
    gettext_noop,
    invalidate_cache,
    ngettext,
    ngettext_lazy,
    npgettext,
    npgettext_lazy,
    override,
    pgettext,
    pgettext_lazy,
    to_locale,
    translate_url,
)

__all__ = [
    # Middleware & views
    "LocaleMiddleware",
    "set_language",
    # URL helpers
    "i18n_patterns",
    "reverse",
    "translate_url",
    # Language state
    "activate",
    "deactivate",
    "deactivate_all",
    "override",
    "get_language",
    # Language info
    "get_language_bidi",
    "get_language_info_list",
    "get_language_switch_urls",
    "get_supported_languages",
    "check_for_language",
    "to_locale",
    # Translation functions
    "gettext",
    "gettext_lazy",
    "gettext_noop",
    "ngettext",
    "ngettext_lazy",
    "pgettext",
    "pgettext_lazy",
    "npgettext",
    "npgettext_lazy",
    "invalidate_cache",
]
