from django import forms
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from .models import Task, TaskRate, TaskUser


class RoleForm(forms.ModelForm):
    class Meta:
        model = TaskUser
        fields = ["type", "user"]
        labels = {"type": _("Role"), "user": _("User")}


class TaskForm(forms.ModelForm):
    days = [(x, _("%(count)s days") % {"count": x}) if x != 1 else (x, _("1 day")) for x in range(6)]
    hours = [(x, _("%(count)s hours") % {"count": x}) if x != 1 else (x, _("1 hour")) for x in range(13)]

    dias = forms.TypedChoiceField(widget=forms.Select, choices=days, coerce=int)
    horas = forms.TypedChoiceField(widget=forms.Select, choices=hours, coerce=int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dias'].choices = [(x, _("1 day") if x == 1 else _("%(count)s days") % {"count": x}) for x in range(6)]
        self.fields['horas'].choices = [(x, _("1 hour") if x == 1 else _("%(count)s hours") % {"count": x}) for x in range(13)]

    class Meta:
        model = Task
        fields = ["id", "name", "description", "dias", "horas", "difficulty"]
        widgets = {"difficulty": forms.HiddenInput()}


class AssignmentStatusForm(forms.Form):
    taskuser_id = forms.IntegerField(min_value=1)
    status = forms.ChoiceField(
        choices=[
            (Task.Status.DOING, Task.Status.DOING.label),
            (Task.Status.PAUSED, Task.Status.PAUSED.label),
            (Task.Status.CANCELED, Task.Status.CANCELED.label),
        ]
    )


class SelfAssessmentForm(forms.Form):
    environment = forms.IntegerField(min_value=1, max_value=5)
    cognition = forms.IntegerField(min_value=1, max_value=5)
    behavior = forms.IntegerField(min_value=1, max_value=5)
    effectiveness = forms.IntegerField(min_value=1, max_value=5)


class StakeholderEvaluationForm(forms.Form):
    effectiveness = forms.IntegerField(min_value=1, max_value=5)


RoleFormSet = formset_factory(RoleForm, extra=0)

class InvitationBatchItemForm(forms.Form):
    email = forms.EmailField(max_length=254)
    type = forms.ChoiceField(choices=Task.UserType.choices)


class PublicJoinRequestForm(forms.Form):
    email = forms.EmailField(max_length=254)
    name = forms.CharField(max_length=150, required=False)
    message = forms.CharField(max_length=500, required=False)


class JoinRequestDecisionForm(forms.Form):
    request_id = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[("approve", _("Approve")), ("reject", _("Reject"))])
    role = forms.ChoiceField(choices=Task.UserType.choices, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") == "approve" and not cleaned.get("role"):
            self.add_error("role", _("A role is required for approval."))
        return cleaned
