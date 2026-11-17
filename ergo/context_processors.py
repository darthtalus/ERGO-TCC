from django.conf import settings
from user_aspects.forms import EffectForm

def ergo_context(request):
    context = {
        'APP_VERSION': getattr(settings, 'APP_VERSION', '1.0.0'),
    }
    if request.user.is_authenticated:
        context['effectiveness_form'] = EffectForm()
    return context
