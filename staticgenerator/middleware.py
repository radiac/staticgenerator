import re
import logging
import sys

from staticgenerator import StaticGenerator, StaticGeneratorException, settings


logger = logging.getLogger('staticgenerator.middleware')


class StaticGeneratorMiddleware(object):
    """
    This requires settings.STATIC_GENERATOR_URLS tuple to match on URLs
    
    Example::
        
        STATIC_GENERATOR_URLS = (
            r'^/$',
            r'^/blog',
        )
        
    """
    urls = tuple([re.compile(url) for url in settings.URLS])
    excluded_urls = tuple([re.compile(url) for url in settings.EXCLUDE_URLS])
    gen = StaticGenerator()

    def process_request(self, request):
        request._static_generator = False

        if getattr(request, 'disable_static_generator', False):
            logger.debug('StaticGeneratorMiddleware: disabled')
            return None

        if (settings.ANONYMOUS_ONLY
             and hasattr(request, 'user')
             and not request.user.is_anonymous()):
            logger.debug('StaticGeneratorMiddleware: '
                         'disabled for logged in user')
            return None

        path = request.path_info

        for url in self.excluded_urls:
            if url.match(path):
                logger.debug('StaticGeneratorMiddleware: '
                             'path %s excluded', path)
                return None

        for url in self.urls:
            if url.match(path):
                request._static_generator = True
                try:
                    logger.debug('StaticGeneratorMiddleware: '
                                 'Trying to publish stale path %s', path)
                    self.gen.publish_stale_path(
                        path,
                        request.META.get('QUERY_STRING', ''),
                        is_ajax=request.is_ajax())
                except StaticGeneratorException:
                    logger.warning(
                        'StaticGeneratorMiddleware: '
                        'failed to publish stale content',
                        exc_info=sys.exc_info(),
                        extra={'request': request})
                return None

        logger.debug('StaticGeneratorMiddleware: path %s not matched', path)
        return None

    def process_response(self, request, response):
        # pylint: disable=W0212
        #         Access to a protected member of a client class

        if  (response.status_code == 200
             and getattr(request, '_static_generator', False)):
            try:
                self.gen.publish_from_path(
                    request.path_info,
                    request.META.get('QUERY_STRING', ''),
                    response.content,
                    is_ajax=request.is_ajax())
            except StaticGeneratorException:
                # Never throw a 500 page because of a failure in
                # writing pages to the cache.  Remember to monitor
                # the site to detect performance regression due to
                # a full disk or insufficient permissions in the
                # cache directory.
                logger.warning(
                    'StaticGeneratorMiddleware: '
                    'failed to publish fresh content',
                    exc_info=sys.exc_info(),
                    extra={'request': request})

        return response
