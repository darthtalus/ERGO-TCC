from django.db import models

class Dimension(models.Model):
    name = models.CharField(max_length=200)
    order = models.IntegerField(unique=False)

    class Meta:
        db_table = 'ergonomic_dimension'
    
    def __str__(self):
        return self.name
