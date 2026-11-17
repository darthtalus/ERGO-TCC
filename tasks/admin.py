from django.contrib import admin

from .models import (
    Task,
    TaskInvitation,
    TaskJoinRequest,
    TaskRate,
    TaskShareLink,
    TaskUser,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'difficulty', 'created_at')
    search_fields = ('name', 'description', 'user__username', 'user__email')
    list_select_related = ('user',)

    # Task deletion is performed only by the guarded application view, which
    # checks authorization and refuses to erase workflow history.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TaskUser)
class TaskUserAdmin(admin.ModelAdmin):
    """Role records are viewable but workflow fields are not editable here.

    State changes and role removal must use the guarded application views so
    authorization, transition rules and audit-history checks are applied.
    """

    list_display = ('id', 'task', 'user', 'type', 'status')
    list_filter = ('type', 'status')
    search_fields = ('task__name', 'user__username', 'user__email')
    list_select_related = ('task', 'user')

    def get_readonly_fields(self, request, obj=None):
        return ('task', 'user', 'type', 'status') if obj else ('status',)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    """Read-only admin base for append-only workflow/audit records."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TaskRate)
class TaskRateAdmin(ReadOnlyAuditAdmin):
    list_display = ('id', 'taskuser', 'user', 'rate_type', 'effectiveness', 'updated_at')
    list_filter = ('rate_type', 'effectiveness')
    search_fields = ('taskuser__task__name', 'user__username', 'user__email')
    list_select_related = ('taskuser__task', 'user')


@admin.register(TaskInvitation)
class TaskInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'task', 'type', 'accepted', 'created_at')
    list_filter = ('type', 'accepted')
    search_fields = ('email', 'task__name')


@admin.register(TaskShareLink)
class TaskShareLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('task__name', 'created_by__email')


@admin.register(TaskJoinRequest)
class TaskJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'share_link', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('email', 'name', 'share_link__task__name')
