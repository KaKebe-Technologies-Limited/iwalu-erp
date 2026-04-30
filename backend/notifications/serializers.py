from rest_framework import serializers
from .models import Notification, NotificationPreference, NotificationTemplate


# ---------- Notification ----------

class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True,
    )
    priority_display = serializers.CharField(
        source='get_priority_display', read_only=True,
    )

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient_id', 'notification_type', 'notification_type_display',
            'channel', 'priority', 'priority_display',
            'title', 'body', 'source_type', 'reference_id',
            'is_read', 'read_at', 'created_at', 'updated_at',
        ]
        read_only_fields = (
            'recipient_id', 'created_at', 'updated_at', 'read_at',
        )


# ---------- Notification Preference ----------

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True,
    )

    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user_id', 'notification_type', 'notification_type_display',
            'channel', 'is_enabled', 'created_at', 'updated_at',
        ]
        read_only_fields = ('user_id', 'created_at', 'updated_at')


class UpdatePreferenceSerializer(serializers.Serializer):
    notification_type = serializers.ChoiceField(
        choices=Notification.TYPE_CHOICES,
    )
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES, default='in_app',
    )
    is_enabled = serializers.BooleanField()


# ---------- Notification Template ----------

class NotificationTemplateSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True,
    )

    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'channel', 'subject', 'body', 'variables',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ('created_at', 'updated_at')
