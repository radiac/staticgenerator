#!/usr/bin/env python
#-*- coding:utf-8 -*-

"""Static file generator for Django."""
import logging
import os
import stat
import tempfile
import urlparse

import shutil

from django.utils.functional import Promise
from django.http import HttpRequest, QueryDict
from django.db.models.base import ModelBase
from django.db.models.manager import Manager
from django.db.models import Model
from django.db.models.query import QuerySet
from django.conf import settings
from django.test.client import RequestFactory
from handlers import DummyHandler


logger = logging.getLogger('staticgenerator')


class StaticGeneratorException(Exception):
    def __init__(self, message, **kwargs):
        super(StaticGeneratorException, self).__init__(message)
        self.__dict__.update(kwargs)


def create_directory(directory):
    """Creates the given directory and missing intermediate directories

    Does nothing if the directory already exists.

    """
    if os.path.exists(directory):
        return
    try:
        os.makedirs(directory)
    except OSError as exc:
        if exc.errno == 17:  # OSError 17 = 'File exists'
            return
    except Exception as exc:
        raise StaticGeneratorException('Could not create directory',
                                       directory=directory)


def hardlink(src, dst, remove_dst=False, ignore_src=False, ignore_dst=False):
    """Hard links the ``src`` file to the ``dst`` file path.

    Arguments:
    * ``src``: the source file
    * ``dst``: the destination hard link path
    * ``remove_dst``: if a true value, first attempts to remove the destination
      file if it exists
    * ``ignore_src``: if a true value, ignores missing source file silently
    * ``ignore_dst``: if a true value, ignores existing destination file
      silently

    """
    create_directory(os.path.dirname(dst))
    if remove_dst:
        try:
            os.remove(dst)
        except OSError as exc:
            if exc.errno != 2:  # 2 = existing destination file not found
                raise StaticGeneratorException('Could not delete file',
                                               dst=dst)
    try:
        os.link(src, dst)
        logger.debug('Linked %s to %s', src, dst)
    except OSError as exc:
        if exc.errno == 2 and ignore_src:
            logger.debug('Source file not found, ignoring',
                         exc_info=True,
                         extra={'src': src})
            return
        if exc.errno == 17 and ignore_dst:
            logger.debug('Destination file already exists, ignoring',
                         exc_info=True,
                         extra={'dst': dst})
            return
        logger.debug('Cannot link file',
                     exc_info=True,
                     extra={'src': src, 'dst': dst})
        raise StaticGeneratorException('Could not link file', src=src, dst=dst)
    except Exception as exc:
        logger.debug('Cannot link file',
                     exc_info=True,
                     extra={'src': src, 'dst': dst})
        raise StaticGeneratorException('Could not link file', src=src, dst=dst)


class StaticGenerator(object):
    """
    The StaticGenerator class is created for Django applications, like a blog,
    that are not updated per request.

    Usage is simple::

        from staticgenerator import quick_publish
        quick_publish('/', Post.objects.live(), FlatPage)

    The class accepts a list of 'resources' which can be any of the 
    following: URL path (string), Model (class or instance), Manager, or 
    QuerySet.

    As of v1.1, StaticGenerator includes file and path deletion::

        from staticgenerator import quick_delete
        quick_delete('/page-to-delete/')

    The most effective usage is to associate a StaticGenerator with a model's
    post_save and post_delete signal.

    The reason for having all the optional parameters is to reduce coupling
    with django in order for more effectively unit testing.
    """

    def __init__(self, *resources):
        self.resources = self.extract_resources(resources)
        self.server_name = self.get_server_name()

        try:
            self.web_root = getattr(settings, 'WEB_ROOT')
        except AttributeError:
            raise StaticGeneratorException('You must specify WEB_ROOT in settings.py')

    def extract_resources(self, resources):
        """Takes a list of resources, and gets paths by type"""
        extracted = []

        for resource in resources:

            # A URL string
            if isinstance(resource, (str, unicode, Promise)):
                extracted.append(str(resource))
                continue

            # A model instance; requires get_absolute_url method
            if isinstance(resource, Model):
                extracted.append(resource.get_absolute_url())
                continue

            # If it's a Model, we get the base Manager
            if isinstance(resource, ModelBase):
                resource = resource._default_manager

            # If it's a Manager, we get the QuerySet
            if isinstance(resource, Manager):
                resource = resource.all()

            # Append all paths from obj.get_absolute_url() to list
            if isinstance(resource, QuerySet):
                extracted += [obj.get_absolute_url() for obj in resource]

        return extracted

    def get_server_name(self):
        '''Tries to get the server name.
        First we look in the django settings.
        If it's not found we try to get it from the current Site.
        Otherwise, return "localhost".
        '''
        try:
            return getattr(settings, 'SERVER_NAME')
        except:
            pass

        try:
            from django.contrib.sites.models import Site
            return Site.objects.get_current().domain
        except:
            print '*** Warning ***: Using "localhost" for domain name. Use django.contrib.sites or set settings.SERVER_NAME to disable this warning.'
            return 'localhost'

    def get_content_from_path(self, path):
        """
        Imitates a basic http request using DummyHandler to retrieve
        resulting output (HTML, XML, whatever)
        """

        request = RequestFactory().get(path)
        # We must parse the path to grab query string
        parsed = urlparse.urlparse(path)
        request.path_info = parsed.path
        request.GET = QueryDict(parsed.query)
        request.META.setdefault('SERVER_PORT', 80)
        request.META.setdefault('SERVER_NAME', self.server_name)
        request.META.setdefault('REMOTE_ADDR', '127.0.0.1')

        handler = DummyHandler()
        try:
            response = handler(request)
        except Exception, err:
            raise StaticGeneratorException("The requested page(\"%s\") raised an exception. Static Generation failed. Error: %s" % (path, str(err)))

        if int(response.status_code) != 200:
            raise StaticGeneratorException("The requested page(\"%s\") returned http code %d. Static Generation failed." % (path, int(response.status_code)))

        return response.content

    def get_query_string_from_path(self, path):
        parts = path.split('?')
        if len(parts) == 1:
            return parts[0], None
        if len(parts) > 2:
            raise StaticGeneratorException('Path %s has multiple query string values' % path)
        return parts[0], parts[1]

    def get_filename_from_path(self, path, query_string, is_ajax=False):
        """
        Returns (filename, directory). None if unable to cache this request.
        Creates index.html for path if necessary
        """
        if path.endswith('/'):
            # Always include a %3F in the file name, even if there are no query
            # parameters.  Using %3F instead of a question mark makes rewriting
            # possible in Apache.  Always including it makes rewriting easier.
            path = '%sindex.html%%3F' % path
        # will not work on windows... meh
        if query_string:
            path += query_string
        if is_ajax:
            # Append an ',ajax' suffix to the file name for AJAX requests.
            # This makes it possible to cache responses which have different
            # content for AJAX requests.
            path += ',ajax'

        filename = (os.path.join(self.web_root, path.lstrip('/'))
                    .encode('utf-8'))
        if len(filename) > 255:
            return None
        return filename

    def _get_publish_data(self, path, query_string, is_ajax):
        # The query_string parameter is only passed from the
        # middleware. If we're generating a page from, e.g.,
        # the `quick_publish` function, the path may still
        # have a query string component.
        if query_string is None:
            path, query_string = self.get_query_string_from_path(path)
        fresh_filename = self.get_filename_from_path(
            u'fresh{0}'.format(path), query_string, is_ajax=is_ajax)
        stale_filename = self.get_filename_from_path(
            u'stale{0}'.format(path), query_string, is_ajax=is_ajax)
        return fresh_filename, stale_filename

    def _publish_stale_file(self, fresh_filename, stale_filename):
        if os.path.isfile(fresh_filename):
            # We already have a fresh version of the resource. Don't
            # overwrite.
            logger.debug('StaticGenerator._publish_stale_file: '
                         '%s already exists', fresh_filename)
            return

        # We don't have a fresh version of the resource.  Either it
        # has never been rendered or it has been invalidated.  Copy a
        # stale version for the duration of the request.
        hardlink(stale_filename, fresh_filename,
                 ignore_src=True, ignore_dst=True)

    def publish_stale_path(self, path, query_string=None, is_ajax=False):
        """Publishes a stale page in the given path if it exists

        This is called from the request middleware

        """
        fresh_filename, stale_filename = self._get_publish_data(
            path, query_string, is_ajax)
        if fresh_filename:  # too long URLs not cached
            self._publish_stale_file(fresh_filename, stale_filename)

    def publish_from_path(self,
                          path,
                          query_string=None,
                          content=None,
                          is_ajax=False):
        """
        Gets filename and content for a path, attempts to create directory if
        necessary, writes to file.  Also hard links the fresh version to a
        stale version in a separate tree.  Serves stale version if available
        while generating content.
        """
        content_path = path

        fresh_filename, stale_filename = self._get_publish_data(path,
                                                                  query_string,
                                                                  is_ajax)

        if not fresh_filename:
            return  # cannot cache

        if not content:
            # The content needs to be fetched with a simulated request to a
            # real view.  Publish a stale version for the duration of the
            # request if available.
            self._publish_stale_file(fresh_filename, stale_filename)
            # Now make the request for the content.  This might take time.
            content = self.get_content_from_path(content_path)

        # Write the content into the fresh version of the cached file.
        fresh_directory = os.path.dirname(fresh_filename)
        create_directory(fresh_directory)
        try:
            f, tmpname = tempfile.mkstemp(dir=fresh_directory)
            os.write(f, content)
            os.close(f)
        except Exception as exc:
            raise StaticGeneratorException(
                'Could not write temporary fresh file',
                fresh_directory=fresh_directory)
        try:
            os.chmod(tmpname,
                     stat.S_IREAD |
                     stat.S_IWRITE |
                     stat.S_IWUSR |
                     stat.S_IRUSR |
                     stat.S_IRGRP |
                     stat.S_IROTH)
            os.rename(tmpname, fresh_filename)
        except Exception:
            logger.warning(
                'Could not chmod or rename fresh file. '
                'Temporary file probably removed by invalidation.',
                exc_info=True,
                extra={'fresh_filename': fresh_filename})
        else:
            # The fresh version of the cached file is now on the disk.  Now
            # create a hard link to it in the stale cache directory.
            hardlink(fresh_filename, stale_filename,
                     remove_dst=True, ignore_dst=True)

    def recursive_delete_from_path(self, path):
        filename = self.get_filename_from_path(
            u'fresh{0}'.format(path), '')
        shutil.rmtree(os.path.dirname(filename), True)

    def delete_from_path(self, path, is_ajax=False):
        """Deletes file, attempts to delete directory"""
        path, query_string = self.get_query_string_from_path(path)
        filename = self.get_filename_from_path(
            u'fresh{0}'.format(path), query_string, is_ajax=is_ajax)

        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            raise StaticGeneratorException('Could not delete file',
                                           filename=filename)

        try:
            os.rmdir(os.path.dirname(filename))
        except OSError:
            # Will fail if a directory is not empty, in which case we don't
            # want to delete it anyway
            pass

    def do_all(self, func):
        return [func(path) for path in self.resources]

    def delete(self):
        return self.do_all(self.delete_from_path)

    def recursive_delete(self):
        return self.do_all(self.recursive_delete_from_path)

    def publish(self):
        return self.do_all(self.publish_from_path)

def quick_publish(*resources):
    return StaticGenerator(*resources).publish()

def quick_delete(*resources):
    return StaticGenerator(*resources).delete()

def recursive_delete(*resources):
    return StaticGenerator(*resources).recursive_delete()
