from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from decimal import Decimal
from datetime import date
from .models import AssetCategory, Asset, AssetAssignment, MaintenanceLog, AssetDisposal
from .serializers import (
    AssetCategorySerializer, AssetListSerializer, AssetDetailSerializer,
    AssetCreateUpdateSerializer, AssetAssignmentSerializer,
    MaintenanceLogSerializer, AssetDisposalSerializer
)
from users.permissions import IsAdminOrManager, IsAccountant

class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'assigned_to_id']
    search_fields = ['asset_code', 'name']
    ordering_fields = ['asset_code', 'acquisition_date', 'cost']

    def get_serializer_class(self):
        if self.action == 'list':
            return AssetListSerializer
        if self.action == 'retrieve':
            return AssetDetailSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return AssetCreateUpdateSerializer
        return AssetListSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign', 'dispose']:
            return [IsAdminOrManager()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from datetime import datetime as dt

        asset = self.get_object()
        assigned_to_id = request.data.get('assigned_to_id')
        assigned_to_type = request.data.get('assigned_to_type', 'employee')
        notes = request.data.get('notes', '')
        assigned_date_input = request.data.get('assigned_date', None)

        if not assigned_to_id:
            return Response({"error": "assigned_to_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and parse assigned_date
        if assigned_date_input:
            try:
                if isinstance(assigned_date_input, date):
                    assigned_date = assigned_date_input
                else:
                    assigned_date = dt.strptime(assigned_date_input, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return Response(
                    {"error": "assigned_date must be in YYYY-MM-DD format"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            assigned_date = date.today()

        # Validate date is not in future
        if assigned_date > date.today():
            return Response(
                {"error": "assigned_date cannot be in the future"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate date is not before asset acquisition
        if assigned_date < asset.acquisition_date:
            return Response(
                {"error": f"assigned_date cannot be before asset acquisition date ({asset.acquisition_date})"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark current assignment as not current
        AssetAssignment.objects.filter(asset=asset, is_current=True).update(
            is_current=False, returned_date=assigned_date
        )

        # Create new assignment
        assignment = AssetAssignment.objects.create(
            asset=asset,
            assigned_to_id=assigned_to_id,
            assigned_to_type=assigned_to_type,
            assigned_date=assigned_date,
            is_current=True,
            notes=notes
        )

        # Update asset
        asset.assigned_to_id = assigned_to_id
        asset.save(update_fields=['assigned_to_id', 'updated_at'])

        return Response({
            "status": "success",
            "message": f"Asset assigned to {assigned_to_type} {assigned_to_id}",
            "assignment_id": assignment.id
        })

    @action(detail=True, methods=['post'], url_path='log-maintenance')
    def log_maintenance(self, request, pk=None):
        asset = self.get_object()
        serializer = MaintenanceLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(asset=asset)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def dispose(self, request, pk=None):
        asset = self.get_object()
        if hasattr(asset, 'disposal'):
            return Response({"error": "Asset is already disposed"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AssetDisposalSerializer(data=request.data)
        if serializer.is_valid():
            disposal = serializer.save(asset=asset)
            return Response({
                "status": "success",
                "message": "Asset disposed",
                "book_value_at_disposal": disposal.book_value_at_disposal,
                "proceeds": disposal.proceeds,
                "gain_or_loss": disposal.gain_or_loss
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAccountant])
    def schedule(self, request):
        year = int(request.query_params.get('year', date.today().year))
        month = request.query_params.get('month')
        category_id = request.query_params.get('category')

        assets = Asset.objects.filter(status=Asset.Status.ACTIVE)
        if category_id:
            assets = assets.filter(category_id=category_id)

        results = []
        total_depreciation_by_month = {m: Decimal('0') for m in range(1, 13)}

        for asset in assets:
            monthly_dep = asset.calculate_monthly_depreciation()
            asset_monthly_values = []
            
            # Simplified schedule: same monthly depreciation for the whole year
            # in a real system we'd check acquisition/disposal dates and useful life expiry
            for m in range(1, 13):
                # Only count depreciation if it was acquired before or during this month
                # and it's within its useful life. For now, we'll keep it simple.
                total_depreciation_by_month[m] += monthly_dep
                asset_monthly_values.append(monthly_dep)

            results.append({
                "asset_code": asset.asset_code,
                "category": asset.category.name,
                "monthly": asset_monthly_values
            })

        month_names = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december'
        ]
        
        totals = {month_names[m-1]: total_depreciation_by_month[m] for m in range(1, 13)}
        if month:
            m_idx = int(month)
            totals = {month_names[m_idx-1]: total_depreciation_by_month[m_idx]}

        # Category breakdown
        categories = AssetCategory.objects.all()
        by_category = []
        for cat in categories:
            cat_assets = assets.filter(category=cat)
            cat_total = sum(a.calculate_monthly_depreciation() for a in cat_assets) * 12
            by_category.append({
                "category": cat.name,
                "total_depreciation_year": cat_total,
                "count_active": cat_assets.count(),
                "count_disposed": Asset.objects.filter(category=cat, status=Asset.Status.DISPOSED).count()
            })

        return Response({
            "year": year,
            "total_depreciation": totals,
            "by_asset": results,
            "by_category": by_category
        })
