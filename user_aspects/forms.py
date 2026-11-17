from django import forms
from .models import UserAspects, Effectiveness, PredefinedAspect
from django.utils.translation import gettext_lazy as _
from units.models import Unit


class AspectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["nome"].widget.attrs["list"] = "list-nomes"
        self.fields["nome"].widget.attrs["autocomplete"] = "off"
        self.fields["nome"].widget.attrs["class"] = "form-control"
        self.fields["valor"].widget.attrs["autocomplete"] = "off"
        self.fields["valor"].widget.attrs["class"] = "form-control"
        
        # Load dynamic choices for unidade from the Unit model
        self.fields["unidade"].widget = forms.Select(choices=[
            (unit.key, unit.name) for unit in Unit.objects.all()
        ])
        self.fields["unidade"].widget.attrs["class"] = "form-select"

    class Meta:
        model = UserAspects
        fields = ["dimension", "nome", "valor", "unidade", "parametrized"]


class EffectForm(forms.ModelForm):
    class Meta:
        model = Effectiveness
        fields = ("effectiveness",)
        widgets = {"effectiveness": forms.HiddenInput()}

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Ex: Kilograms, Liters...")})
        }


class PredefinedAspectForm(forms.ModelForm):
    class Meta:
        model = PredefinedAspect
        fields = ["dimension", "name", "language"]
        widgets = {
            "dimension": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Ex: Stress, Posture...")}),
            "language": forms.TextInput(attrs={"class": "form-control", "placeholder": "pt-br, en..."}),
        }
