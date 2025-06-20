# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Users, AccountNotificationSetting

class CustomUserAdmin(UserAdmin):
    model = Users
    list_display = ['email', 'name', 'is_staff']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'name', 'picture', 'password', 'areas_of_interest')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'picture', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )
    search_fields = ('email',)

class AccountNotificationSettingAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'email_notifications',
        'push_notifications',
        'notify_on_new_hotspot_data',
        'notify_on_new_deforestation_data',
        'updated_at'
    ]

admin.site.register(Users, CustomUserAdmin)
admin.site.register(AccountNotificationSetting, AccountNotificationSettingAdmin)