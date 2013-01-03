#!/usr/bin/env python
#-*- coding:utf-8 -*-

# pylint: disable=E1101
#         Instance of <class> has no <member>

from contextlib import nested
from django.db.models.query import QuerySet
from django.test.utils import override_settings
from django.test import TestCase
from mock import ANY, call, Mock, patch
from nose.tools import raises
import os
import shutil
from staticgenerator import (StaticGenerator,
                             StaticGeneratorException)
import staticgenerator
from staticgenerator.tests.models import Model


def queryset_mock_factory(*args):
    """Creates a mock queryset with the given model instances"""
    queryset = QuerySet()
    queryset._result_cache = args
    return queryset


class StaticGeneratorWithoutWebRootSetting_Tests(TestCase):
    @raises(StaticGeneratorException)
    def test_not_having_web_root_raises(self):
        StaticGenerator()

    @override_settings(WEB_ROOT='test_web_root_1294128189')
    def test_staticgenerator_keeps_track_of_web_root(self):
        instance = StaticGenerator()

        self.assertEqual('test_web_root_1294128189', instance.web_root)


@override_settings(WEB_ROOT='test_web_root')
class StaticGeneratorWithoutServerNameSetting_Tests(TestCase):
    def test_get_server_name_gets_name_from_site(self):
        with patch('django.contrib.sites.models'
                   '.Site.objects.get_current') as get_current:
            get_current().domain = 'custom_domain'

            instance = StaticGenerator()

        self.assertEqual('custom_domain', instance.server_name)

    def test_get_server_name_as_localhost_by_default(self):
        instance = StaticGenerator()

        self.assertEqual('localhost', instance.server_name)


@override_settings(WEB_ROOT='test_web_root',
                   SERVER_NAME='localhost')
class StaticGeneratorWithWebRootSetting_Tests(TestCase):
    def tearDown(self):
        shutil.rmtree('test_web_root', ignore_errors=True)

    def test_can_create_staticgenerator(self):
        instance = StaticGenerator()

        self.assertTrue(instance)
        self.assertIsInstance(instance, StaticGenerator)

    @override_settings(SERVER_NAME='some_random_server')
    def test_get_server_name_gets_name_from_settings(self):
        instance = StaticGenerator()

        self.assertEqual('some_random_server', instance.server_name)

    def test_extract_resources_when_resource_is_a_str(self):
        resources_mock = "some_str"

        instance = StaticGenerator(resources_mock)

        self.assertEqual(1, len(instance.resources))
        self.assertEqual('some_str', instance.resources[0])

    def test_extract_resources_when_resource_is_a_model(self):
        resources_mock = Model(url='some_model_url')

        instance = StaticGenerator(resources_mock)

        self.assertEqual(1, len(instance.resources))
        self.assertEqual('some_model_url', instance.resources[0])

    def test_extract_resources_when_resource_is_a_model_base(self):
        instance_mock = Model(url='some_url1')
        instance_mock2 = Model(url='some_url2')
        queryset = queryset_mock_factory(instance_mock, instance_mock2)
        with patch.object(Model.objects, 'all') as model_objects_all:
            model_objects_all.return_value = queryset

            instance = StaticGenerator(Model)

        self.assertEqual(2, len(instance.resources))
        self.assertEqual('some_url1', instance.resources[0])
        self.assertEqual('some_url2', instance.resources[1])

    def test_get_content_from_path(self):
        response_mock = Mock(content='foo', status_code=200)
        instance = StaticGenerator()
        with patch.object(staticgenerator, 'DummyHandler') as DummyHandler:
            DummyHandler().return_value = response_mock

            result = instance.get_content_from_path('/some_path')

        self.assertEqual('foo', result)

    def test_get_filename_from_path(self):
        instance = StaticGenerator()

        result = instance.get_filename_from_path('/foo/bar', '')

        self.assertEqual('test_web_root/foo/bar', result)

    def test_get_filename_from_path_when_path_ends_with_slash(self):
        instance = StaticGenerator()

        result = instance.get_filename_from_path('/foo/bar/', '')

        self.assertEqual('test_web_root/foo/bar/index.html%3F', result)

    def test_publish_raises_when_unable_to_create_current_folder(self):
        instance = StaticGenerator()
        with nested(patch('os.path.exists'),
                    patch('os.makedirs'),
                    self.assertRaises(StaticGeneratorException)
                    ) as (exists, makedirs, cm):
            exists.return_value = False
            makedirs.side_effect = ValueError('message')

            instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual('Could not create directory', str(cm.exception))
        self.assertEqual('test_web_root/fresh', cm.exception.directory)

    def test_publish_raises_when_unable_to_create_stale_folder(self):
        real_makedirs = os.makedirs

        def makedirs_mock(directory, *args):
            if directory == 'test_web_root/stale':
                raise ValueError()
            real_makedirs(directory, *args)

        instance = StaticGenerator()
        with nested(patch('os.path.exists'),
                    patch('os.makedirs'),
                    self.assertRaises(StaticGeneratorException)
                    ) as (exists, makedirs, cm):
            exists.return_value = False
            makedirs.side_effect = makedirs_mock

            instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual('Could not create directory', str(cm.exception))
        self.assertEqual('test_web_root/stale', cm.exception.directory)

    def test_publish_raises_when_unable_to_create_temp_file(self):
        instance = StaticGenerator()
        with nested(patch('tempfile.mkstemp'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (mkstemp, cm):
            mkstemp.side_effect = ValueError('message')

            instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual('Could not write temporary fresh file',
                         str(cm.exception))
        self.assertEqual('test_web_root/fresh', cm.exception.fresh_directory)

    def test_publish_fails_silently_when_unable_to_chmod_temp_file(self):
        instance = StaticGenerator()
        with patch('os.chmod') as chmod:
            chmod.side_effect = ValueError('message')

            instance.publish_from_path('/some_path', content='some_content')

        self.assertFalse(os.path.exists('test_web_root/fresh/some_path'))

    def test_publish_fails_silently_when_unable_to_rename_temp_file(self):
        instance = StaticGenerator()
        with patch('os.rename') as rename:
            rename.side_effect = ValueError('message')

            instance.publish_from_path('/some_path', content='some_content')

        self.assertFalse(os.path.exists('test_web_root/fresh/some_path'))

    def test_publish_raises_when_unable_to_hard_link_stale_file(self):
        instance = StaticGenerator()
        with nested(patch('os.link'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (link, cm):
            link.side_effect = OSError(2, 'message')

            instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual('Could not link file', str(cm.exception))
        self.assertEqual('test_web_root/fresh/some_path', cm.exception.src)
        self.assertEqual('test_web_root/stale/some_path', cm.exception.dst)

    def test_publish_from_path_creates_current_file(self):
        instance = StaticGenerator()

        instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual('some_content',
                         open('test_web_root/fresh/some_path').read())

    def test_publish_from_path_hard_links_stale_file(self):
        instance = StaticGenerator()

        instance.publish_from_path('/some_path', content='some_content')

        self.assertEqual(os.stat('test_web_root/fresh/some_path').st_ino,
                         os.stat('test_web_root/stale/some_path').st_ino)

    def test_publish_from_path_serves_stale_file_temporarily(self):
        instance = StaticGenerator()
        os.makedirs('test_web_root/stale')
        open('test_web_root/stale/some_path', 'w').write('stale content')

        def handler(_request):
            """A mock request handler

            At the time of the request, the current content should be hard
            linked to the stale version.

            """
            current_content = open('test_web_root/fresh/some_path').read()
            return Mock(content=('this content replaces {0!r}'
                                 .format(current_content)),
                        status_code=200)

        with patch.object(staticgenerator, 'DummyHandler') as DummyHandler:
            DummyHandler.return_value = handler

            instance.publish_from_path('/some_path')

        self.assertEqual("this content replaces 'stale content'",
                         open('test_web_root/fresh/some_path').read())

    def test_delete_raises_when_unable_to_delete_file(self):
        instance = StaticGenerator()
        with nested(patch('os.path.exists'),
                    patch('os.remove'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (exists, remove, cm):
            exists.return_value = True
            remove.side_effect = ValueError

            instance.delete_from_path('/some_path')

        self.assertEqual('Could not delete file', str(cm.exception))
        self.assertEqual('test_web_root/fresh/some_path',
                         cm.exception.filename)

    def test_delete_ignores_folder_delete_when_unable_to_delete_folder(self):
        instance = StaticGenerator()
        rmdir = Mock(side_effect=OSError)
        with nested(patch('os.path.exists', Mock(return_value=True)),
                    patch('os.remove'),
                    patch('os.rmdir', rmdir)):

            instance.delete_from_path('/some_path')

        rmdir.assert_called_once_with('test_web_root/fresh')

    def test_delete_from_path_deletes_current_file(self):
        instance = StaticGenerator()
        remove = Mock()
        with nested(patch('os.path.exists', Mock(return_value=True)),
                    patch('os.remove', remove)):

            instance.delete_from_path('/some_path')

        remove.assert_called_once_with('test_web_root/fresh/some_path')

    def test_delete_from_path_does_not_delete_stale_file(self):
        instance = StaticGenerator()
        remove = Mock()
        with nested(patch('os.path.exists', Mock(return_value=True)),
                    patch('os.remove', remove)):

            instance.delete_from_path('/some_path')

        self.assertNotIn(call('test_web_root/stale/some_path'),
                         remove.call_args_list)

    def test_publish_loops_through_all_resources(self):
        instance = StaticGenerator('/some_path_1', '/some_path_2')
        rename = Mock(wraps=os.rename)
        with nested(patch('os.rename', rename),
                    patch.object(instance, 'get_content_from_path',
                                 Mock(return_value='some_content'))):

            instance.publish()

        rename.assert_has_calls([
            call(ANY, 'test_web_root/fresh/some_path_1'),
            call(ANY, 'test_web_root/fresh/some_path_2')])

    def test_delete_loops_through_all_resources(self):
        instance = StaticGenerator('/some_path', '/some_path_2')
        remove = Mock()
        with nested(patch('os.path.exists', Mock(return_value=True)),
                    patch('os.remove', remove)):

            instance.delete()

        remove.assert_has_calls([call('test_web_root/fresh/some_path'),
                                 call('test_web_root/fresh/some_path_2')])

    def test_can_create_dummy_handler(self):
        handler = staticgenerator.DummyHandler()
        handler.load_middleware = lambda: True
        handler.get_response = lambda request: 'bar'
        middleware_method = lambda request, response: (request, response)
        handler._response_middleware = [middleware_method]

        result = handler('foo')

        self.assertEqual(('foo', 'bar'), result)

    def test_bad_request_raises_proper_exception(self):
        response_mock = Mock(content='foo', status_code=500)
        instance = StaticGenerator()
        with nested(patch('staticgenerator.DummyHandler'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (handler_mock, cm):
            handler_mock.return_value = Mock(return_value=response_mock)

            instance.get_content_from_path('/some_path')

        self.assertEqual(('The requested page("/some_path") returned '
                          'http code 500. Static Generation failed.'),
                         str(cm.exception))

    def test_not_found_raises_proper_exception(self):
        response_mock = Mock(content='foo', status_code=404)
        instance = StaticGenerator()
        with nested(patch('staticgenerator.DummyHandler'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (handler_mock, cm):
            handler_mock.return_value = Mock(return_value=response_mock)

            instance.get_content_from_path('/some_path')

        self.assertEqual(('The requested page("/some_path") returned '
                          'http code 404. Static Generation failed.'),
                         str(cm.exception))

    def test_request_exception_raises_proper_exception(self):
        instance = StaticGenerator()
        with nested(patch('staticgenerator.DummyHandler'),
                    self.assertRaises(StaticGeneratorException)
                   ) as (handler_mock, cm):
            handler_mock.return_value = Mock(
                side_effect=ValueError('exception'))

            instance.get_content_from_path('/some_path')

        self.assertEqual('The requested page("/some_path") raised an '
                         'exception. Static Generation failed. '
                         'Error: exception',
                         str(cm.exception))
