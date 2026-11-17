from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

# from django.contrib.auth.models import User
from accounts.models import CustomUser


class UserAspects(models.Model):
    class Meta:
        db_table = 'aspect_measurement'

    class Dimension(models.TextChoices):
        BEHAVIOR = "BEHAVIOR", _("Behavior")
        COGNITION = "COGNITION", _("Cognition")
        ENVIRONMENT = "ENVIRONMENT", _("Environment")

    class Unidades(models.TextChoices):
        CELCIUS = "CELCIUS", _("ºC")
        FARENHEIT = "FARENHEIT", _("ºF")
        ESCALA1A5 = "ESCALA1A5", _("Scale (1 to 5)")
        DECIBEIS = "DECIBEIS", _("Decibels")
        HERTZ = "HERTZ", _("Hertz")
        LUMENS = "LUMENS", _("Lumens")
        TEMPO = "TEMPO", _("Time")

    dimension = models.CharField(max_length=15, choices=Dimension.choices)
    nome = models.CharField(max_length=250)
    valor = models.CharField(max_length=50)
    parametrized = models.PositiveSmallIntegerField(default=0)
    watched = models.BooleanField(default=True)
    user = models.ForeignKey(CustomUser, on_delete=models.DO_NOTHING)
    unidade = models.CharField(max_length=100)

    @property
    def range(self):
        return range(1, self.parametrized + 1)

    @property
    def completerange(self):
        return range(5 - self.parametrized)

    @property
    def unidade_display(self):
        # Check hardcoded choices first
        for key, label in self.Unidades.choices:
            if self.unidade == key:
                return label
        
        # If not found, try to find in Unit model
        from units.models import Unit
        unit = Unit.objects.filter(key=self.unidade).first()
        if unit:
            return unit.name
            
        return self.unidade

    def to_dict(self):
        return {
            "id": self.id,
            "user_dimention": self.user_dimension.to_dict(),
            "nome": self.nome,
            "valor": self.valor,
        }


class Effectiveness(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="effectiviness"
    )
    day = models.DateField(auto_now_add=True)
    effectiveness = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    class Meta:
        db_table = 'daily_effectiveness'
        unique_together = ('user', 'day')


class UserAspectHistory(models.Model):
    class Meta:
        db_table = 'measurement_history'

    dimension = models.CharField(max_length=15, choices=UserAspects.Dimension.choices)
    nome = models.CharField(max_length=250)
    valor = models.CharField(max_length=50)
    parametrized = models.PositiveSmallIntegerField(default=0)
    watched = models.BooleanField(default=True)
    unidade = models.CharField(max_length=100)
    effectiveness = models.ForeignKey(
        Effectiveness, related_name="history", on_delete=models.CASCADE
    )

    @property
    def unidade_display(self):
        # Check hardcoded choices first
        for key, label in UserAspects.Unidades.choices:
            if self.unidade == key:
                return label
        
        # If not found, try to find in Unit model
        from units.models import Unit
        unit = Unit.objects.filter(key=self.unidade).first()
        if unit:
            return unit.name
            
        return self.unidade

class DimensionUnit(models.Model):
    dimension = models.CharField(max_length=15, choices=UserAspects.Dimension.choices)
    unit = models.ForeignKey('units.Unit', on_delete=models.CASCADE, related_name="dimension_configs", null=True)

    class Meta:
        db_table = 'dimension_unit_mapping'
        unique_together = ('dimension', 'unit')
        verbose_name = _("Dimension Unit Configuration")
        verbose_name_plural = _("Dimension Unit Configurations")

    def __str__(self):
        return f"{self.get_dimension_display()} - {self.unit.name if self.unit else '?'}"


class PredefinedAspect(models.Model):
    dimension = models.CharField(max_length=15, choices=UserAspects.Dimension.choices)
    name = models.CharField(max_length=250)
    language = models.CharField(max_length=10, default='pt-br')

    class Meta:
        db_table = 'aspect_template'
        unique_together = ('dimension', 'name', 'language')
        verbose_name = _("Predefined Aspect")
        verbose_name_plural = _("Predefined Aspects")

    def __str__(self):
        return f"{self.get_dimension_display()}: {self.name}"
