from django.db import models
from django.utils.translation import gettext_lazy as _


class Unit(models.Model):
    class Meta:
        db_table = 'measurement_unit'

    key = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name