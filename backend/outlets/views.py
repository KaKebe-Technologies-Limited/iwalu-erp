from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from users.permissions import IsAdminOrManager
from .models import Outlet
from .serializers import OutletSerializer


class OutletViewSet(viewsets.ModelViewSet):
    queryset = Outlet.objects.all()
    serializer_class = OutletSerializer
    search_fields = ['name', 'address']
    filterset_fields = ['outlet_type', 'is_active']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]
