from setuptools import setup

version = '1.4.2-g2.0'

setup(name='staticgenerator',
      version=version,
      description="StaticGenerator for Django",
      author="Jared Kuolt",
      author_email="me@superjared.com",
      url="http://superjared.com/projects/static-generator/",
      packages=['staticgenerator',
                'staticgenerator.management',
                'staticgenerator.management.commands']
)
