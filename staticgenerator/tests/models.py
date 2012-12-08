from django.db import models


class Model(models.Model):
    url = models.CharField(max_length=20)

    def get_absolute_url(self):
        return self.url
