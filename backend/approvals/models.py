from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

class ApprovalPolicy(models.Model):
    """
    Defines approval requirements for a transaction type.
    Example: "Any purchase order > 5M requires manager approval, then admin sign-off"
    """
    class ResourceType(models.TextChoices):
        PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
        LEAVE_REQUEST = 'leave_request', 'Leave Request'
        PAYROLL_RUN = 'payroll_run', 'Payroll Run'
        CASH_REQUISITION = 'cash_requisition', 'Cash Requisition'
        STOCK_ADJUSTMENT = 'stock_adjustment', 'Stock Adjustment'

    name = models.CharField(max_length=200, help_text='e.g., "PO Approval — High Value"')
    resource_type = models.CharField(max_length=50, choices=ResourceType.choices)
    
    # Threshold (optional; if not set, applies to all transactions of type)
    min_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Minimum transaction amount to trigger approval'
    )
    max_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Leave blank for unlimited upper bound'
    )
    
    # Approval chain (JSON: list of levels, each with role + min_approvers count)
    # Example: [
    #   {"level": 1, "role": "manager", "min_approvers": 1, "description": "Manager review"},
    #   {"level": 2, "role": "admin", "min_approvers": 1, "description": "Admin sign-off"}
    # ]
    approval_levels = models.JSONField(
        help_text='List of approval levels: [{level, role, min_approvers, description}]'
    )
    
    # Auto-approval: if matching conditions, skip approval (e.g., amount < 100K)
    auto_approve_if_under = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Auto-approve if amount <= this threshold'
    )
    
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['resource_type', 'min_amount']
        indexes = [
            models.Index(fields=['resource_type', 'is_active']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_resource_type_display()})"

    def clean(self):
        if self.max_amount is not None and self.min_amount is not None:
            if self.max_amount <= self.min_amount:
                raise ValidationError("max_amount must be > min_amount")
        
        # Validate approval_levels JSON structure
        if self.approval_levels:
            if not isinstance(self.approval_levels, list):
                raise ValidationError("approval_levels must be a list")
            try:
                for level in self.approval_levels:
                    assert 'level' in level
                    assert 'role' in level
                    assert 'min_approvers' in level
            except (AssertionError, TypeError):
                raise ValidationError("approval_levels must be list of {level, role, min_approvers, description}")

    def matches_amount(self, amount: Decimal) -> bool:
        """Check if this policy applies to given amount."""
        if amount is None:
            return False
        if self.min_amount is not None and amount < self.min_amount:
            return False
        if self.max_amount is not None and amount > self.max_amount:
            return False
        return True

    def should_auto_approve(self, amount: Decimal) -> bool:
        """Check if amount qualifies for auto-approval."""
        return (
            self.auto_approve_if_under is not None and
            amount is not None and
            amount <= self.auto_approve_if_under
        )


class ApprovalRequest(models.Model):
    """
    Approval workflow instance. Created when transaction meets policy threshold.
    Tracks all approval actions through its lifecycle.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting Approval'
        APPROVED = 'approved', 'Fully Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled (transaction cancelled)'
        AUTO_APPROVED = 'auto_approved', 'Auto-Approved'

    policy = models.ForeignKey(ApprovalPolicy, on_delete=models.PROTECT)
    
    # Resource reference (polymorphic: IntegerField + resource_type)
    resource_type = models.CharField(
        max_length=50, choices=ApprovalPolicy.ResourceType.choices
    )
    resource_id = models.IntegerField(
        help_text='FK to PurchaseOrder, LeaveRequest, PayrollPeriod, etc. (cross-schema safe)'
    )
    
    # Requestor
    requested_by_id = models.IntegerField(
        help_text='User who created the transaction (cross-schema safe)'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    
    # Amount (for audit trail + threshold checking)
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Transaction amount for audit'
    )
    
    # Status lifecycle
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Approval chain state (JSON: [{level, role, approved_count, pending_count}])
    # Updated as approvals come in
    approval_chain_state = models.JSONField(default=list, blank=True)
    
    notes = models.TextField(blank=True, help_text='Initial notes from requestor')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'resolved_at']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
        unique_together = ('resource_type', 'resource_id')  # Only one approval request per resource

    def __str__(self):
        return f"Approval for {self.get_resource_type_display()} #{self.resource_id} ({self.status})"

    @property
    def is_resolved(self):
        return self.status in [self.Status.APPROVED, self.Status.REJECTED, self.Status.AUTO_APPROVED, self.Status.CANCELLED]

    @property
    def pending_level(self):
        """Return the current approval level awaiting action."""
        if self.is_resolved:
            return None
        for level_data in self.approval_chain_state:
            approved_count = level_data.get('approved_count', 0)
            min_approvers = level_data.get('min_approvers', 1)
            if approved_count < min_approvers:
                return level_data.get('level')
        return None

    def get_approvers_at_level(self, level: int):
        """Return User IDs of approvers required at given level."""
        policy_level = next(
            (l for l in self.policy.approval_levels if l['level'] == level),
            None
        )
        if not policy_level:
            return []
        role = policy_level['role']
        
        # Query tenant users by role (requires User model query; use cross-schema via shared auth)
        from users.models import User
        users = User.objects.filter(role=role, is_active=True)
        return [u.id for u in users]

    def all_levels_approved(self):
        """Check if all approval levels have sufficient approvals."""
        for level_data in self.approval_chain_state:
            if level_data.get('approved_count', 0) < level_data.get('min_approvers', 1):
                return False
        return True


class ApprovalAction(models.Model):
    """
    Single approval or rejection at an approval level.
    Audit trail of who approved/rejected and when.
    """
    class Action(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    approval_request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name='actions'
    )
    
    # Approver
    actor_id = models.IntegerField(
        help_text='User ID of approver (cross-schema safe)'
    )
    
    # Action
    level = models.PositiveIntegerField(help_text='Approval level (1, 2, 3, etc.)')
    action = models.CharField(max_length=10, choices=Action.choices)
    
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level', 'created_at']
        indexes = [
            models.Index(fields=['approval_request', 'level']),
        ]

    def __str__(self):
        return f"Level {self.level} {self.get_action_display()} at {self.created_at}"
