from django import forms
from django.utils.translation import gettext_lazy as _
from .models import CustomUser

class UserEditForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': _('Leave blank to keep current password')}),
        label=_("New Password")
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'birthdate', 'company', 'country', 'role', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'birthdate': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),

            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



    def __init__(self, *args, **kwargs):
        is_superadmin = kwargs.pop('is_superadmin', False)
        super(UserEditForm, self).__init__(*args, **kwargs)
        if not is_superadmin:
            # If not superadmin, they can't change the role or password
            self.fields['role'].disabled = True
            self.fields['role'].help_text = _("Only SuperAdmins can change user roles.")
            self.fields['new_password'].disabled = True
            self.fields['new_password'].help_text = _("Only SuperAdmins can change user passwords.")
            
            # Prevent blocking a SuperAdmin if the editor is just an Admin
            if self.instance and self.instance.role == 'SUPERADMIN':
                self.fields['is_active'].disabled = True
                self.fields['is_active'].help_text = _("Only SuperAdmins can block other SuperAdmins.")

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        if password:
            import re
            if len(password) < 6:
                raise forms.ValidationError(_("Password must be at least 6 characters long."))
            if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
                raise forms.ValidationError(_("Password must contain at least one letter and one number."))
        return password



class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'birthdate', 'company', 'country']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'birthdate': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
        }
