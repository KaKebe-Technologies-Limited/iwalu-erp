from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager
from .models import Notification, NotificationPreference, NotificationTemplate
from .serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer, UpdatePreferenceSerializer,
    NotificationTemplateSerializer,
)
from . import services


class NotificationViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    """
    List, retrieve, and delete notifications for the authenticated user.
    Supports filtering by type, channel, priority, and read status.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'channel', 'priority']
    search_fields = ['title', 'body']
    ordering_fields = ['created_at', 'priority']

    def get_queryset(self):
        """Scoped to the authenticated user's notifications only."""
        qs = Notification.objects.filter(recipient_id=self.request.user.pk)
        is_read = self.request.query_params.get('is_read')
        if is_read == 'true':
            qs = qs.filter(read_at__isnull=False)
        elif is_read == 'false':
            qs = qs.filter(read_at__isnull=True)
        return qs

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = services.get_unread_count(request.user.pk)
        return Response({'unread_count': count})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = services.mark_read(pk, request.user.pk)
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        notification_type = request.data.get('notification_type')
        # Validate notification_type if provided
        valid_types = {t[0] for t in Notification.TYPE_CHOICES}
        if notification_type and notification_type not in valid_types:
            return Response(
                {'error': f'Invalid notification_type. Choose from: {", ".join(sorted(valid_types))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = services.mark_all_read(request.user.pk, notification_type)
        return Response({'marked_read': count})


class NotificationPreferenceViewSet(mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin,
                                    viewsets.GenericViewSet):
    """
    Manage notification preferences for the authenticated user.
    Use the update-preference action to create/toggle preferences.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'channel', 'is_enabled']

    def get_queryset(self):
        return NotificationPreference.objects.filter(user_id=self.request.user.pk)

    @action(detail=False, methods=['post'], url_path='update-preference')
    def update_preference(self, request):
        serializer = UpdatePreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pref, created = NotificationPreference.objects.update_or_create(
            user_id=request.user.pk,
            notification_type=data['notification_type'],
            channel=data['channel'],
            defaults={'is_enabled': data['is_enabled']},
        )
        return Response(
            NotificationPreferenceSerializer(pref).data,
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
        )


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for notification templates. Admin/Manager only for writes.
    """
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'channel', 'is_active']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def preview(self, request, pk=None):
        """Preview a template with sample context data."""
        template = self.get_object()
        context = request.data.get('context', {})
        subject, body = template.render(context)
        return Response({'subject': subject, 'body': body})
