from django.db import models


class Aspect(models.Model):
    """Legacy placeholder kept importable for compatibility.

    The active aspect models live in user_aspects. Keeping this model abstract
    avoids creating an unused database table if the legacy app is enabled.
    """

    class Meta:
        abstract = True
