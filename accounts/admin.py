from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, CustomUserGroup, CustomUserPermission


class CustomUserGroupInline(admin.TabularInline):
    model = CustomUserGroup
    extra = 1


class CustomUserPermissionInline(admin.TabularInline):
    model = CustomUserPermission
    extra = 1


class CustomUserAdmin(UserAdmin):
    inlines = [CustomUserGroupInline, CustomUserPermissionInline]

    filter_horizontal = ()

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (
            'Personal Info',
            {'fields': ('first_name', 'last_name', 'email', 'company', 'birthdate', 'country')},
        ),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'password1', 'password2'),
            },
        ),
    )


admin.site.register(CustomUser, CustomUserAdmin)
