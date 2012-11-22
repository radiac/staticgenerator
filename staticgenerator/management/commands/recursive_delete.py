from django.core.management.base import LabelCommand
from staticgenerator import recursive_delete


class Command(LabelCommand):
    help = 'Invalidates the on-disk cache recursively'
    args = '<resource>'
    label = 'resource'

    requires_model_validation = False

    def handle_label(self, resource, **options):
        recursive_delete(resource)
