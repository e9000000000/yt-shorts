import sys
from django.apps import AppConfig


class SegsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "segs"


    def ready(self):
        if "runserver" in sys.argv:
            from . import bg
            bg.execute()
