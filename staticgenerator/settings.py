"""
Settings for staticgenerator

Override these by setting new values in your global settings file
"""
from django.conf import settings
from django.dispatch import receiver
from django.test.signals import setting_changed

from staticgenerator.exceptions import StaticGeneratorException


def load_settings():
    g = globals()
    
    # STATIC_GENERATOR_ROOT
    # Root path for the generated static files
    # If not found, falls back to old WEB_ROOT setting
    # If still not found, raises StaticGeneratorException
    g['ROOT'] = getattr(settings, 'STATIC_GENERATOR_ROOT',
        getattr(settings, 'WEB_ROOT', None)
    )
    if g['ROOT'] is None:
        raise StaticGeneratorException(
            'You must specify STATIC_GENERATOR_ROOT in your settings'
        )

    # STATIC_GENERATOR_ANONYMOUS_ONLY
    # Default: False
    g['ANONYMOUS_ONLY'] = getattr(
        settings, 'STATIC_GENERATOR_ANONYMOUS_ONLY', False
    )

    # STATIC_GENERATOR_AUTHENTICATED_COOKIE
    # If set, set a cookie with this name for authenticated users (value "1").
    # Allows the web server to bypass static files and force requests to Django
    # without relying on the sessionid cookie being present or absent.
    # Suggested: "is_auth"
    # Default: None
    g['AUTHENTICATED_COOKIE'] = getattr(
        settings, 'STATIC_GENERATOR_AUTHENTICATED_COOKIE', None
    )
    
    # STATIC_GENERATOR_URLS
    # Default: [r'^/$']
    g['URLS'] = getattr(settings, 'STATIC_GENERATOR_URLS', [r'^/$'])

    # STATIC_GENERATOR_EXCLUDE_URLS
    # Default: []
    g['EXCLUDE_URLS'] = getattr(settings, 'STATIC_GENERATOR_EXCLUDE_URLS', [])

load_settings()

@receiver(setting_changed)
def _reload_settings(sender, **kwargs):
    load_settings()
