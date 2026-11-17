from django.db import models
from dimensions.models import Dimension

class UserDimension(models.Model):
    class Meta:
        db_table = 'user_dimension_assignment'

    user_id = models.IntegerField()
    dimension = models.ForeignKey(Dimension, on_delete=models.DO_NOTHING)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
        }