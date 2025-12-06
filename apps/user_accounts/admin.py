from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # The fields to display in the list view
    list_display = ('email', 'username', 'fullname', 'department', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'department')
    search_fields = ('email', 'username', 'fullname')
    ordering = ('email',)

    # Fieldsets control how the "Edit User" form looks
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('fullname', 'username', 'position', 'department', 'mfo')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_approving_officer', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    
    # This is required for custom user models that use email as username
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'fullname', 'department', 'password'),
        }),
    )
