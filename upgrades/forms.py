from django import forms
from django.utils.translation import gettext_lazy as _

from .models import RecurringTaskRule, SensorReading, TaskComment, TaskStartChecklist, TaskTemplate
from .validators import ALLOWED_ATTACHMENT_CONTENT_TYPES


class BootstrapMixin:
    def _apply_bootstrap(self):
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = (css + ' form-check-input').strip()
            else:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class TaskCommentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Add a comment, observation, blocker, or decision...')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attachment'].widget.attrs['accept'] = '.pdf,.png,.jpg,.jpeg,.txt,.csv,.doc,.docx,.xls,.xlsx'
        self._apply_bootstrap()

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if not attachment:
            return attachment
        content_type = getattr(attachment, 'content_type', None)
        if content_type and content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise forms.ValidationError(
                _('Unsupported attachment content type. Use PDF, image, text, CSV, Word, or Excel files.')
            )
        return attachment


class TaskTemplateForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = ['name', 'description', 'dias', 'horas', 'difficulty', 'checklist']
        labels = {
            'name': _('Name'), 'description': _('Description'), 'dias': _('Days'),
            'horas': _('Hours'), 'difficulty': _('Difficulty'), 'checklist': _('Checklist'),
        }
        widgets = {
            'description': forms.TextInput(attrs={'maxlength': 250}),
            'difficulty': forms.NumberInput(attrs={'min': 0, 'max': 5}),
            'checklist': forms.Textarea(attrs={'rows': 4, 'placeholder': _('One checklist item per line')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['difficulty'].help_text = _('Use a value from 0 to 5.')
        self._apply_bootstrap()


class RecurringTaskRuleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = RecurringTaskRule
        fields = ['template', 'frequency', 'next_run', 'is_active']
        labels = {
            'template': _('Template'), 'frequency': _('Frequency'),
            'next_run': _('Next run'), 'is_active': _('Is active'),
        }
        widgets = {'next_run': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['template'].queryset = TaskTemplate.objects.filter(owner=owner)
        self._apply_bootstrap()


class TaskStartChecklistForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TaskStartChecklist
        fields = [
            'environment_ok',
            'lighting_ok',
            'noise_ok',
            'fatigue_low',
            'clarity_ok',
            'acceptance_criteria_ok',
        ]
        labels = {
            'environment_ok': _('Environment is adequate'),
            'lighting_ok': _('Lighting is adequate'),
            'noise_ok': _('Noise level is acceptable'),
            'fatigue_low': _('Fatigue is low'),
            'clarity_ok': _('Task objective is clear'),
            'acceptance_criteria_ok': _('Acceptance criteria are clear'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class SensorReadingForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SensorReading
        fields = [
            'source',
            'temperature_c',
            'humidity_percent',
            'noise_db',
            'luminosity_lux',
            'air_quality_index',
            'note',
        ]
        labels = {
            'source': _('Source'),
            'temperature_c': _('Temperature (°C)'),
            'humidity_percent': _('Humidity (%)'),
            'noise_db': _('Noise (dB)'),
            'luminosity_lux': _('Luminosity (lux)'),
            'air_quality_index': _('Air quality index'),
            'note': _('Note'),
        }
        widgets = {
            'temperature_c': forms.NumberInput(attrs={'step': '0.01', 'min': -50, 'max': 70}),
            'humidity_percent': forms.NumberInput(attrs={'step': '0.01', 'min': 0, 'max': 100}),
            'noise_db': forms.NumberInput(attrs={'step': '0.01', 'min': 0, 'max': 200}),
            'luminosity_lux': forms.NumberInput(attrs={'step': '0.01', 'min': 0, 'max': 200000}),
            'air_quality_index': forms.NumberInput(attrs={'step': '0.01', 'min': 0, 'max': 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
