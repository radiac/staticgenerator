INSTALLED_APPS = 'django_nose', 'staticgenerator.tests'
TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}
SECRET_KEY = '123'
STATIC_GENERATOR_ROOT = 'test_web_root'
