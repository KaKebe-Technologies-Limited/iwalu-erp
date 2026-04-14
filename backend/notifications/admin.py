from django.contrib import admin
from .models import Notification, NotificationPreference, NotificationTemplate


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient_id', 'notification_type', 'channel', 'priority', 'read_at', 'created_at')
    list_filter = ('notification_type', 'channel', 'priority')
    search_fields = ('title', 'body')
    date_hierarchy = 'created_at'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'notification_type', 'channel', 'is_enabled')
    list_filter = ('notification_type', 'channel', 'is_enabled')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('notification_type', 'channel', 'subject', 'is_active')
    list_filter = ('notification_type', 'channel', 'is_active')
