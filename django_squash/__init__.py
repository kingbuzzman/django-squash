import pkg_resources

default_app_config = 'django_squash.apps.DjangoSquashConfig'

__version__ = pkg_resources.get_distribution('django').version
