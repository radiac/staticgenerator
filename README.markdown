# StaticGenerator for Django

## Introduction

How many CPU cycles do you suppose are wasted on blogs that are generated every request? Wouldn’t it make more sense to generate them only when they’re updated? StaticGenerator is a re-usable app for Django that makes it easy to create static files for lightning fast performance.

## Fork

This fork from [mrj0's version](https://github.com/mrj0/staticgenerator) includes patches contributed and used by [2General Ltd](http://www.2general.com/).

The mrj0 version is itself a fork from the main branch in order to add patches from [bolhoed](https://bitbucket.org/bolhoed/mixedcase/src/tip/project/staticgenerator/). See the details at [mixedCase.nl](http://mixedcase.nl/articles/2010/11/16/serving-5000-pages-second-django/).

### Differences introduced by mrj0 and 2general

#### The ability to only cache for anonymous users and to exclude urls

Example `settings.py`:

    WEB_ROOT = os.path.join(os.path.dirname(__file__), 'generated')
    
    STATIC_GENERATOR_ANONYMOUS_ONLY = True
    
    STATIC_GENERATOR_URLS = (
        r'^/$',
        r'^/(articles|projects|about)',
    )
    
    STATIC_GENERATOR_EXCLUDE_URLS = (
         r'\.xml$',
         r'^/articles/search',
         r'^/articles/feed',
         r'^/articles/comments/posted',
    )

Another way to always exclude a view from being cached is to use the `@disable_static_generator` decorator:

    from staticgenerator.decorators import disable_static_generator
    
    @disable_static_generator
    def myview(request)
        # ...

#### Mitigation of the dog-piling effect

Each page is cached as two copies. After invalidation, the stale copy is served until the page has been generated. This avoids the dog-piling (a.k.a. "thundering herd") problem.

There is still a small window at the start of the WSGI request when another request might arrive and not yet get served with the stale content. If the duration of this window isn't sufficiently short to prevent dog-piling for your traffic, you might be better of regenerating most visited pages instead of invalidating them.

#### Cache AJAX requests separately

AJAX requests are cached separately from other requests. This is useful for sites which return different content for AJAX requests than for normal requests. This feature can't currently be switched off, although it probably should.

#### Apache-friendly file names

Question marks in URLs are encoded as the string `%3F` in file names, because it's not possible to stop Apache from stripping out the query string out before finding files from disk. Also, a trailing `%3F` is included even if there is no query string. This allows for simpler rewrite rules.

#### More robust middleware

The middleware now works even if the request object has no `user` attribute. This can happen e.g. when using [mediagenerator's](https://github.com/2general/django-mediagenerator/) middleware in development mode.

#### Management command for invalidating the cache

You can run the `manage.py recursive_delete /` command to invalidate the whole cache.  Use subpaths to only invalidate a part of the cache.

## Download

You can get 2General's fork of StaticGenerator by cloning with Git or using `pip`:

    git clone git://github.com/2general/staticgenerator.git
    pip install -e git+git://github.com/2general/staticgenerator.git#egg=staticgenerator

You can get the official version of StaticGenerator without the mrj0 and 2General contributions using `easy_install` or `pip`:

    easy_install staticgenerator
    pip install staticgenerator
    
Or download from the [Python Package Index](http://pypi.python.org/pypi/staticgenerator/1.4.1).

## Usage

There are two ways to generate the static files. Both setups first require `WEB_ROOT` to be set in `settings.py`:

    WEB_ROOT = '/var/www/example.com/public/'

### Method 1 (preferred): Middleware

As of StaticGenerator 1.3, Middleware is available to generate the file only when the URL is requested. This solves the 404 Problem (see below).

First, add Regexes of URLs you want to cache to `settings.py` like so:

    STATIC_GENERATOR_URLS = (
        r'^/$',
        r'^/blog',
        r'^/about',
    )
    
Second, add the Middleware to `MIDDLEWARE_CLASSES`:

    MIDDLEWARE_CLASSES = (
        ...snip...
        'staticgenerator.middleware.StaticGeneratorMiddleware',
        'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
        ...snip...
    )
    
**Note**: You must place the StaticGeneratorMiddleware before FlatpageFallbackMiddleware if you use it.
    
When the pages are accessed for the first time, the body of the page is saved into a static file. This is completely transparent to the end-user. When the page or an associated object has changed, simply delete the cached file (See notes on Signals).

### Method 2: Generate on Save

The second method works by saving the cache file on save. This method fakes a request to get the appropriate content. In this example we want to publish our home page, all live Posts and all FlatPages:

    # Passing url, a QuerySet and Model
    from staticgenerator import quick_publish
    quick_publish('/', Post.objects.live(), FlatPage)

Deleting files and paths is just as easy:

    from staticgenerator import quick_delete
    quick_delete('/path-to-delete/')

*Note: Directory deletion fails silently while failing to delete a file will raise an exception.*

#### The "404 Problem"

The second method suffers from a problem herein called the "404 problem". Say you have a blog post that is not yet to be published. When you save it, the file created is actually a 404 message since the blog post is not actually available to the public. Using the older method you'd have to re-save the object to generate the file again.

The new method solves this because it saves the file only when the URL is accessed successfully (read: only when the HTTP status is 200).

### Using Signals

Integrating with existing models is easy using [Django’s signal dispatcher](http://code.djangoproject.com/wiki/Signals). Simply create a function to delete your models, and connect to the dispatcher:

    from django.contrib.flatpages.models import FlatPage
    from blog.models import Post
    from django.dispatch import dispatcher
    from django.db.models import signals
    from staticgenerator import quick_delete

    def delete(sender, instance):
        quick_delete(instance, '/')

    dispatcher.connect(delete, sender=Post, signal=signals.post_save)
    dispatcher.connect(delete, sender=FlatPage, signal=signals.post_save)

Every time you save a Post or FlatPage it deletes the static file (notice that I add '/' so my homepage is deleted as well). What happens when a comment is added? Just delete the corresponding page:

    from django.contrib.comments.models import Comment, FreeComment

    def publish_comment(sender, instance):
        quick_delete(instance.get_content_object())

    dispatcher.connect(publish_comment, sender=Comment, signal=signals.post_save)
    dispatcher.connect(publish_comment, sender=FreeComment, signal=signals.post_save)
    
## Configure your front-end

### Sample Nginx configuration

This configuration snippet shows how Nginx can automatically show the index.html page generated by StaticGenerator, and pass all Django requests to Apache.

    # This example configuration only shows parts relevant to a Django app
    http {
    
        upstream django {
            # Apache/mod_python running on port 7000
            server example.com:7000;
        }
    
        server {
            server_name  example.com;
            root   /var/www/myproject/generated/fresh;

            location / {
                default_type  text/html;

                if ($http_x_requested_with = XMLHttpRequest) {
                    set $is_ajax ",ajax";
                }

                if (-f $request_filename/index.html%3F$args$is_ajax) {
                    rewrite (.*)/ $1/index.html%3F$args$is_ajax;
                    break;
                }

                if (!-f $request_filename%3F$args$is_ajax) {
                    proxy_pass http://django;
                    break;
                }
            }
        }
    }
    
## It’s not for Everything

The beauty of the generator is that you choose when and what urls are made into static files. Obviously a contact form or search form won’t work this way, so we just leave them as regular Django requests. In your front-end http server (you are using a front-end web server, right?) just set the URLs you want to be served as static and they’re already being served.

## Feedback

Love it? Hate it? [Let me know what you think!](http://superjared.com/contact/)