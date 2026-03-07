from rest_framework import serializers
from .models import Outlet


class OutletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = ['id', 'name', 'outlet_type', 'address', 'phone',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
