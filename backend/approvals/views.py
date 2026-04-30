from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ApprovalPolicy, ApprovalRequest, ApprovalAction
from .serializers import ApprovalPolicySerializer, ApprovalRequestSerializer, ApprovalActionSerializer
from notifications.services import notify_approval_required
from users.models import User

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'manager']

class ApprovalPolicyViewSet(viewsets.ModelViewSet):
    queryset = ApprovalPolicy.objects.all()
    serializer_class = ApprovalPolicySerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAdminOrManager()]

class ApprovalRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApprovalRequest.objects.all()
    serializer_class = ApprovalRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        from django.db.models import Q

        # Users can see requests they created OR all pending requests (role check enforced in approve action)
        queryset = ApprovalRequest.objects.filter(
            Q(requested_by_id=user.id) | Q(status='pending')
        ).distinct()

        # For safety, approvers must pass role validation in the approve() action itself
        return queryset

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def approve(self, request, pk=None):
        approval_request = self.get_object()
        user = request.user
        
        if approval_request.is_resolved:
            return Response(
                {"error": "This request is already resolved."},
                status=status.HTTP_409_CONFLICT
            )
            
        pending_level = approval_request.pending_level
        level_data = next((l for l in approval_request.approval_chain_state if l['level'] == pending_level), None)
        
        if not level_data or level_data['role'] != user.role:
            raise PermissionDenied("You do not have the required role to approve at this level.")
            
        # Check if user already approved at this level
        if ApprovalAction.objects.filter(
            approval_request=approval_request,
            actor_id=user.id,
            level=pending_level
        ).exists():
            return Response(
                {"error": "You have already approved this request at this level."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create action
        comment = request.data.get('comment', '')
        ApprovalAction.objects.create(
            approval_request=approval_request,
            actor_id=user.id,
            level=pending_level,
            action=ApprovalAction.Action.APPROVED,
            comment=comment
        )
        
        # Update chain state
        level_data['approved_count'] = level_data.get('approved_count', 0) + 1
        approval_request.save()
        
        # Check if fully approved
        if approval_request.all_levels_approved():
            approval_request.status = ApprovalRequest.Status.APPROVED
            approval_request.resolved_at = timezone.now()
            approval_request.save()
            
            # Update the source resource
            self._update_resource_status(approval_request, 'approved')
            
            return Response({
                "status": "success",
                "message": "Fully approved. Resource is now active.",
                "new_status": "approved"
            })
            
        # If level is finished but more levels remain
        if level_data['approved_count'] >= level_data['min_approvers']:
            next_level = approval_request.pending_level
            # Notify next level approvers
            self._notify_next_approvers(approval_request, next_level)
            
            return Response({
                "status": "success",
                "next_level": next_level,
                "message": f"Approved at level {pending_level}. Waiting for next level.",
                "new_status": "pending"
            })
            
        return Response({
            "status": "success",
            "message": f"Approved at level {pending_level}. More approvals needed at this level.",
            "new_status": "pending"
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reject(self, request, pk=None):
        approval_request = self.get_object()
        user = request.user
        
        if approval_request.is_resolved:
            return Response(
                {"error": "This request is already resolved."},
                status=status.HTTP_409_CONFLICT
            )
            
        pending_level = approval_request.pending_level
        level_data = next((l for l in approval_request.approval_chain_state if l['level'] == pending_level), None)
        
        if not level_data or level_data['role'] != user.role:
            raise PermissionDenied("You do not have the required role to reject at this level.")
            
        comment = request.data.get('comment', '')
        if not comment:
            return Response(
                {"error": "A comment is required for rejection."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create action
        ApprovalAction.objects.create(
            approval_request=approval_request,
            actor_id=user.id,
            level=pending_level,
            action=ApprovalAction.Action.REJECTED,
            comment=comment
        )
        
        # Terminate workflow
        approval_request.status = ApprovalRequest.Status.REJECTED
        approval_request.resolved_at = timezone.now()
        approval_request.save()
        
        # Update the source resource
        self._update_resource_status(approval_request, 'rejected')
        
        return Response({
            "status": "success",
            "message": f"Rejected at level {pending_level}.",
            "new_status": "rejected"
        })

    def _update_resource_status(self, approval_request, status_value):
        """Update the actual resource (PO, Leave, etc.) status based on approval result."""
        resource_type = approval_request.resource_type
        resource_id = approval_request.resource_id
        
        if resource_type == 'purchase_order':
            from inventory.models import PurchaseOrder
            po = PurchaseOrder.objects.filter(id=resource_id).first()
            if po:
                po.status = 'submitted' if status_value == 'approved' else 'rejected'
                po.save()
        elif resource_type == 'leave_request':
            from hr.models import LeaveRequest
            lr = LeaveRequest.objects.filter(id=resource_id).first()
            if lr:
                lr.status = 'approved' if status_value == 'approved' else 'rejected'
                lr.save()
        elif resource_type == 'payroll_run':
            from hr.models import PayrollPeriod
            pp = PayrollPeriod.objects.filter(id=resource_id).first()
            if pp:
                pp.status = 'processing' if status_value == 'approved' else 'rejected'
                pp.save()
        elif resource_type == 'cash_requisition':
            from finance.models import CashRequisition
            cr = CashRequisition.objects.filter(id=resource_id).first()
            if cr:
                cr.status = 'approved' if status_value == 'approved' else 'rejected'
                cr.save()

    def _notify_next_approvers(self, approval_request, level):
        """Send notifications to approvers at the given level."""
        approver_ids = approval_request.get_approvers_at_level(level)
        try:
            requester = User.objects.get(id=approval_request.requested_by_id)
            requester_name = requester.get_full_name() or requester.username
        except User.DoesNotExist:
            requester_name = "Unknown"
            
        notify_approval_required(
            transaction_type=approval_request.get_resource_type_display(),
            amount=approval_request.amount or "N/A",
            requester_name=requester_name,
            reference_id=approval_request.id,
            recipient_ids=approver_ids
        )
