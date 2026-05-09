from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, IntegrityError
from django.db.models import F, Sum
from django.db.models.functions import Greatest
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from .models import Project, ProjectTask, ProjectExpense, ProjectTimeEntry
from .serializers import (
    ProjectSerializer, ProjectTaskSerializer,
    ProjectExpenseSerializer, ProjectTimeEntrySerializer
)
from approvals.models import ApprovalRequest, ApprovalPolicy
from system_config.models import SystemConfig
from users.permissions import IsAdminOrManager


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'project_number']
    ordering_fields = ['created_at', 'start_date', 'budget']
    filterset_fields = ['status', 'manager_id']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        date_str = timezone.now().strftime('%Y%m%d')
        for attempt in range(10):
            count = Project.objects.filter(
                project_number__startswith=f'PRJ-{date_str}'
            ).count() + 1 + attempt
            project_number = f"PRJ-{date_str}-{str(count).zfill(4)}"
            try:
                serializer.save(project_number=project_number, status=Project.Status.DRAFT)
                return
            except IntegrityError:
                if attempt == 9:
                    raise
                continue

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        project = self.get_object()
        if project.status != Project.Status.DRAFT:
            return Response({'error': 'Only draft projects can be submitted.'}, status=status.HTTP_400_BAD_REQUEST)

        config = SystemConfig.objects.first()
        threshold = config.project_approval_threshold if config else Decimal('0')

        if threshold > 0 and project.budget >= threshold:
            policy = ApprovalPolicy.objects.filter(resource_type='project', is_active=True).first()
            if policy:
                approval_req = ApprovalRequest.objects.create(
                    policy=policy,
                    resource_type='project',
                    resource_id=project.id,
                    requested_by_id=request.user.id,
                    amount=project.budget
                )
                project.approval_request = approval_req
                project.status = Project.Status.PENDING_APPROVAL
                project.save()
                return Response({
                    'status': 'pending_approval',
                    'approval_id': approval_req.id,
                    'message': 'Project submitted for approval.'
                })

        project.status = Project.Status.ACTIVE
        project.save()
        return Response({'status': 'active', 'message': 'Project activated.'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        project = self.get_object()
        if project.status != Project.Status.ACTIVE:
            return Response({'error': 'Only active projects can be completed.'}, status=status.HTTP_400_BAD_REQUEST)
        project.status = Project.Status.COMPLETED
        project.save()
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        project = self.get_object()
        if project.status in (Project.Status.COMPLETED, Project.Status.CANCELLED):
            return Response(
                {'error': f'Cannot cancel a {project.status} project.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        project.status = Project.Status.CANCELLED
        project.save()
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['post'])
    def hold(self, request, pk=None):
        project = self.get_object()
        if project.status != Project.Status.ACTIVE:
            return Response({'error': 'Only active projects can be put on hold.'}, status=status.HTTP_400_BAD_REQUEST)
        project.status = Project.Status.ON_HOLD
        project.save()
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        project = self.get_object()
        if project.status != Project.Status.ON_HOLD:
            return Response({'error': 'Only on-hold projects can be resumed.'}, status=status.HTTP_400_BAD_REQUEST)
        project.status = Project.Status.ACTIVE
        project.save()
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['get'])
    def profitability(self, request, pk=None):
        project = self.get_object()
        expenses_by_cat = project.expenses.values('category').annotate(total=Sum('amount'))
        total_hours = project.time_entries.aggregate(total=Sum('hours'))['total'] or 0

        task_summary = {
            'todo': project.tasks.filter(status=ProjectTask.Status.TODO).count(),
            'in_progress': project.tasks.filter(status=ProjectTask.Status.IN_PROGRESS).count(),
            'done': project.tasks.filter(status=ProjectTask.Status.DONE).count(),
            'cancelled': project.tasks.filter(status=ProjectTask.Status.CANCELLED).count(),
        }

        return Response({
            'project_number': project.project_number,
            'name': project.name,
            'budget': project.budget,
            'actual_cost': project.actual_cost,
            'budget_remaining': project.budget_remaining,
            'is_over_budget': project.is_over_budget,
            'budget_utilisation_pct': project.budget_utilisation_pct,
            'expenses_by_category': {e['category']: e['total'] for e in expenses_by_cat},
            'total_hours_logged': total_hours,
            'task_summary': task_summary
        })


class ProjectTaskViewSet(viewsets.ModelViewSet):
    queryset = ProjectTask.objects.all()
    serializer_class = ProjectTaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['project', 'status', 'priority', 'assigned_to_id']
    search_fields = ['title']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    def perform_update(self, serializer):
        new_status = serializer.validated_data.get('status')
        if new_status == ProjectTask.Status.DONE:
            serializer.save(completed_at=timezone.now())
        elif new_status and new_status != ProjectTask.Status.DONE:
            serializer.save(completed_at=None)
        else:
            serializer.save()


class ProjectExpenseViewSet(viewsets.ModelViewSet):
    queryset = ProjectExpense.objects.all()
    serializer_class = ProjectExpenseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'category', 'expense_date']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        with transaction.atomic():
            expense = serializer.save(incurred_by_id=self.request.user.id)
            Project.objects.filter(pk=expense.project_id).update(actual_cost=F('actual_cost') + expense.amount)

    def perform_update(self, serializer):
        with transaction.atomic():
            old_amount = self.get_object().amount
            expense = serializer.save()
            diff = expense.amount - old_amount
            if diff != 0:
                Project.objects.filter(pk=expense.project_id).update(actual_cost=F('actual_cost') + diff)

    def perform_destroy(self, instance):
        with transaction.atomic():
            Project.objects.filter(pk=instance.project_id).update(
                actual_cost=Greatest(F('actual_cost') - instance.amount, Decimal('0'))
            )
            instance.delete()


class ProjectTimeEntryViewSet(viewsets.ModelViewSet):
    queryset = ProjectTimeEntry.objects.all()
    serializer_class = ProjectTimeEntrySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'staff_id', 'date', 'task']

    def get_permissions(self):
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(staff_id=self.request.user.id)
