from django.contrib import admin

from .models import (
    RecurringTaskOccurrence,
    RecurringTaskRule,
    SensorApiToken,
    SensorReading,
    TaskChecklistItem,
    TaskComment,
    TaskReview,
    TaskStartChecklist,
    TaskTemplate,
)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'created_at')
    search_fields = ('task__name', 'user__email', 'content')


@admin.register(TaskReview)
class TaskReviewAdmin(ReadOnlyAuditAdmin):
    list_display = ('taskuser', 'reviewed_by', 'status', 'cycle_number', 'created_at')
    list_filter = ('status',)


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'difficulty', 'dias', 'horas', 'created_at')
    search_fields = ('name', 'description')


@admin.register(RecurringTaskRule)
class RecurringTaskRuleAdmin(admin.ModelAdmin):
    list_display = ('template', 'owner', 'frequency', 'next_run', 'is_active')
    list_filter = ('frequency', 'is_active')


@admin.register(RecurringTaskOccurrence)
class RecurringTaskOccurrenceAdmin(admin.ModelAdmin):
    list_display = ('rule', 'scheduled_for', 'task', 'created_at')
    list_filter = ('scheduled_for',)


@admin.register(TaskStartChecklist)
class TaskStartChecklistAdmin(admin.ModelAdmin):
    list_display = ('taskuser', 'answered_by', 'risk_score', 'created_at')


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('task', 'position', 'text', 'is_completed', 'completed_by')
    list_filter = ('is_completed',)


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('user', 'captured_at', 'source', 'temperature_c', 'noise_db', 'luminosity_lux')
    list_filter = ('source',)


@admin.register(SensorApiToken)
class SensorApiTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'prefix', 'is_active', 'created_at', 'last_used_at')
    readonly_fields = ('key_hash',)
