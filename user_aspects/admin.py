from django.contrib import admin

from .models import UserAspects, Effectiveness, UserAspectHistory, DimensionUnit, PredefinedAspect

class UserAspectsAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'valor')

admin.site.register(UserAspects, UserAspectsAdmin)
admin.site.register(Effectiveness)
admin.site.register(UserAspectHistory)
admin.site.register(DimensionUnit)
admin.site.register(PredefinedAspect)