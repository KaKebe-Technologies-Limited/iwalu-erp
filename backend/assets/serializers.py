from rest_framework import serializers
from .models import AssetCategory, Asset, AssetAssignment, MaintenanceLog, AssetDisposal
from decimal import Decimal

class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = '__all__'


class AssetAssignmentSerializer(serializers.ModelSerializer):
    duration_days = serializers.ReadOnlyField()

    class Meta:
        model = AssetAssignment
        fields = '__all__'


class MaintenanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceLog
        fields = '__all__'


class AssetDisposalSerializer(serializers.ModelSerializer):
    gain_or_loss = serializers.ReadOnlyField()

    class Meta:
        model = AssetDisposal
        fields = '__all__'


class AssetListSerializer(serializers.ModelSerializer):
    category = AssetCategorySerializer(read_only=True)
    book_value = serializers.ReadOnlyField()
    is_fully_depreciated = serializers.ReadOnlyField()
    age_months = serializers.ReadOnlyField()

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_code', 'name', 'category', 'acquisition_date',
            'cost', 'accumulated_depreciation', 'book_value',
            'useful_life_years', 'status', 'assigned_to_id', 'location',
            'is_fully_depreciated', 'age_months'
        ]


class AssetDetailSerializer(serializers.ModelSerializer):
    category = AssetCategorySerializer(read_only=True)
    assignments = AssetAssignmentSerializer(many=True, read_only=True)
    maintenance_logs = MaintenanceLogSerializer(many=True, read_only=True)
    disposal = AssetDisposalSerializer(read_only=True)
    
    book_value = serializers.ReadOnlyField()
    is_fully_depreciated = serializers.ReadOnlyField()
    age_months = serializers.ReadOnlyField()
    depreciation_remaining = serializers.ReadOnlyField()
    monthly_depreciation = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_code', 'name', 'category', 'acquisition_date',
            'cost', 'accumulated_depreciation', 'book_value',
            'useful_life_years', 'depreciation_method', 'depreciation_rate_pct',
            'status', 'assigned_to_id', 'location', 'residual_value', 'notes',
            'photo_url', 'is_fully_depreciated', 'age_months',
            'depreciation_remaining', 'monthly_depreciation',
            'assignments', 'maintenance_logs', 'disposal',
            'created_at', 'updated_at'
        ]

    def get_monthly_depreciation(self, obj):
        return obj.calculate_monthly_depreciation()


class AssetCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=AssetCategory.objects.all(), source='category', write_only=True
    )

    class Meta:
        model = Asset
        fields = [
            'asset_code', 'name', 'category_id', 'acquisition_date',
            'cost', 'useful_life_years', 'depreciation_method',
            'depreciation_rate_pct', 'location', 'assigned_to_id',
            'residual_value', 'notes', 'photo_url', 'status'
        ]

    def create(self, validated_data):
        # Set defaults from category if not provided
        category = validated_data.get('category')
        if category:
            if 'useful_life_years' not in validated_data:
                validated_data['useful_life_years'] = category.default_useful_life_years
            if 'depreciation_method' not in validated_data:
                validated_data['depreciation_method'] = category.default_depreciation_method
            if 'depreciation_rate_pct' not in validated_data:
                validated_data['depreciation_rate_pct'] = category.default_depreciation_rate_pct
        
        asset = super().create(validated_data)
        
        # Create initial assignment if assigned_to_id is provided
        assigned_to_id = validated_data.get('assigned_to_id')
        if assigned_to_id:
            AssetAssignment.objects.create(
                asset=asset,
                assigned_to_id=assigned_to_id,
                assigned_to_type='employee', # Default to employee
                assigned_date=validated_data.get('acquisition_date', date.today()),
                is_current=True
            )
            
        return asset
