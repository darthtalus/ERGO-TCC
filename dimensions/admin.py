from django.contrib import admin

from .models import Dimension

class DimensionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    list_display_links = ('id', 'name')

admin.site.register(Dimension, DimensionAdmin)