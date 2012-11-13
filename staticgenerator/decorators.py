from django.utils.decorators import available_attrs
from functools import wraps


def disable_static_generator(view_func):
    """Decorator which prevents caching the response from a view on disk

    Flags the view with a ``disable_static_generator`` attribute so
    staticgenerator won't ever save its response on the filesystem.

    Example::

        @disable_static_generator
        def myview(request):
            # ...

    """
    # We could just do view_func.disable_static_generator = True, but
    # decorators are nicer if they don't have side-effects, so we return a new
    # function.
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.disable_static_generator = True
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)
