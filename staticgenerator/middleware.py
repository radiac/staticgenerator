import re
from django.conf import settings
from staticgenerator import StaticGenerator, StaticGeneratorException

class StaticGeneratorMiddleware(object):
    """
    This requires settings.STATIC_GENERATOR_URLS tuple to match on URLs
    
    Example::
        
        STATIC_GENERATOR_URLS = (
            r'^/$',
            r'^/blog',
        )
        
    """
    urls = tuple([re.compile(url) for url in settings.STATIC_GENERATOR_URLS])
    excluded_urls = tuple([re.compile(url) for url in getattr(settings, 'STATIC_GENERATOR_EXCLUDE_URLS', [])])
    gen = StaticGenerator()
    
    def process_response(self, request, response):
        path = request.path_info
        query_string = request.META.get('QUERY_STRING', '')
        if response.status_code == 200:
            if  (getattr(settings, 'STATIC_GENERATOR_ANONYMOUS_ONLY', False)
                 and hasattr(request, 'user')
                 and not request.user.is_anonymous()):
                return response

            if getattr(request, 'disable_static_generator', False):
                return response

            excluded = False
            for url in self.excluded_urls:
                if url.match(path):
                    excluded = True
                    break

            if not excluded:
                for url in self.urls:
                    if url.match(path):
                        try:
                            self.gen.publish_from_path(
                                path,
                                query_string,
                                response.content,
                                is_ajax=request.is_ajax())
                        except StaticGeneratorException:
                            # Never throw a 500 page because of a failure in
                            # writing pages to the cache.  Remember to monitor
                            # the site to detect performance regression due to
                            # a full disk or insufficient permissions in the
                            # cache directory.
                            pass
                        break

        return response
