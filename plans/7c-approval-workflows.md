# Phase 7c Implementation Plan: Approval Workflows

**Backend only** (tenant-scoped, new `approvals` app)  
**Estimated scope**: 4 models, 8 endpoints, ~40 tests, 3 integration hooks  
**New apps**: `approvals` (tenant-scoped)  
**Tenant-scoped**: Yes

---

## Overview

Implements multi-level approval workflows for business-critical transactions:
1. **Approval policies**: Admin defines approval chains by transaction type, amount range, required role
2. **Approval requests**: System auto-creates when transaction threshold met (PO, leave, payroll, requisition)
3. **Approval actions**: Users at each level approve/reject; system tracks history
4. **Integration hooks**: Wire into PurchaseOrder, LeaveRequest, PayrollPeriod, CashRequisition (new model)
5. **Notifications**: Integration with existing `notifications` app

---

## Models

### `ApprovalPolicy` (in `approvals/models.py`)

```python
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
        from django.core.exceptions import ValidationError
        if self.max_amount is not None and self.min_amount is not None:
            if self.max_amount <= self.min_amount:
                raise ValidationError("max_amount must be > min_amount")
        
        # Validate approval_levels JSON structure
        if self.approval_levels:
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
            amount <= self.auto_approve_if_under
        )
```

### `ApprovalRequest` (in `approvals/models.py`)

```python
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
        return self.status in [self.Status.APPROVED, self.Status.REJECTED, self.Status.AUTO_APPROVED]

    @property
    def pending_level(self):
        """Return the current approval level awaiting action."""
        if self.is_resolved:
            return None
        for level_data in self.approval_chain_state:
            if level_data.get('pending_count', 0) > 0:
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
        min_count = policy_level['min_approvers']
        
        # Query tenant users by role (requires User model query; use cross-schema via shared auth)
        from users.models import User
        users = User.objects.filter(role=role, is_active=True)[:min_count]
        return [u.id for u in users]

    def all_levels_approved(self):
        """Check if all approval levels have sufficient approvals."""
        for level_data in self.approval_chain_state:
            if level_data.get('approved_count', 0) < level_data.get('min_approvers', 1):
                return False
        return True
```

### `ApprovalAction` (in `approvals/models.py`)

```python
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
```

### `CashRequisition` (in `finance/models.py` — NEW model for HR/Finance)

```python
class CashRequisition(models.Model):
    """
    Employee cash request (advance, imprests, operational petty cash).
    Requires manager approval, optionally accountant approval for amounts > threshold.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'
        SETTLED = 'settled', 'Settled (employee returned balance)'

    class RequisitionType(models.TextChoices):
        PETTY_CASH = 'petty_cash', 'Petty Cash'
        EMPLOYEE_ADVANCE = 'employee_advance', 'Employee Advance'
        OPERATIONAL = 'operational', 'Operational Expense'

    requisition_number = models.CharField(
        max_length=50, unique=True,
        help_text='Auto-generated: REQ-YYYY-##### '
    )
    requisition_type = models.CharField(max_length=30, choices=RequisitionType.choices)
    
    requested_by_id = models.IntegerField(help_text='Employee ID requesting cash')
    requested_at = models.DateTimeField(auto_now_add=True)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    
    purpose = models.TextField(help_text='Why cash is needed')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    approved_by_id = models.IntegerField(
        null=True, blank=True,
        help_text='Final approver (manager or accountant)'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    paid_by_id = models.IntegerField(null=True, blank=True, help_text='Cashier who paid out')
    paid_at = models.DateTimeField(null=True, blank=True)
    
    settled_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Amount returned (if not fully expended)'
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'requested_by_id']),
        ]

    def __str__(self):
        return f"{self.requisition_number} - {self.amount} {self.currency} ({self.status})"
```

---

## Endpoints

All endpoints return 403 Forbidden if user lacks approval permission.

### `GET /api/approvals/`

List approval requests for current user (either as requestor or approver).

**Permissions**: `IsAuthenticated`

**Query params**:
- `status` — pending, approved, rejected, auto_approved, cancelled
- `resource_type` — purchase_order, leave_request, payroll_run, cash_requisition, stock_adjustment
- `page` — pagination

**Response (200 OK)**:
```json
{
  "count": 12,
  "results": [
    {
      "id": 5,
      "resource_type": "purchase_order",
      "resource_id": 23,
      "requested_by_id": 10,
      "amount": 5500000,
      "status": "pending",
      "pending_level": 1,
      "approval_chain": [
        {"level": 1, "role": "manager", "approved_count": 0, "min_approvers": 1}
      ],
      "requested_at": "2026-04-27T10:00:00Z",
      "notes": "Bulk fuel supplier order"
    }
  ]
}
```

---

### `GET /api/approvals/{id}/`

Full approval request detail including all actions.

**Permissions**: `IsAuthenticated` (user must be requestor or approver)

**Response (200 OK)**:
```json
{
  "id": 5,
  "resource_type": "purchase_order",
  "resource_id": 23,
  "amount": 5500000,
  "status": "pending",
  "pending_level": 1,
  "approval_chain": [
    {
      "level": 1,
      "role": "manager",
      "description": "Manager review",
      "min_approvers": 1,
      "approved_count": 0,
      "pending_count": 1,
      "pending_from": ["Manager A", "Manager B"]
    }
  ],
  "actions": [
    // empty if no approvals yet
  ],
  "requested_by_id": 10,
  "requested_at": "2026-04-27T10:00:00Z",
  "resolved_at": null,
  "notes": "Bulk order"
}
```

---

### `POST /api/approvals/{id}/approve/`

Approve at current level.

**Permissions**: `IsAuthenticated` (user must have required role)

**Request body**:
```json
{
  "comment": "Looks good. Cost is reasonable and supplier verified."
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "next_level": 2,
  "message": "Approved at level 1. Waiting for admin sign-off.",
  "new_status": "pending"  // still pending if more levels
}
```

**Response (200 OK) — if final approval**:
```json
{
  "status": "success",
  "message": "Fully approved. Resource is now active.",
  "new_status": "approved"
}
```

**Errors**:
- 400: Already approved by this user at this level
- 403: User doesn't have required role
- 404: Approval request not found
- 409: Approval already resolved (not pending)

---

### `POST /api/approvals/{id}/reject/`

Reject approval request. Cancels workflow; transaction must be resubmitted.

**Permissions**: `IsAuthenticated` (user must have required role at pending level)

**Request body**:
```json
{
  "comment": "Amount exceeds budget. Please resubmit with revised quantity."
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Rejected at level 1.",
  "new_status": "rejected"
}
```

---

### `GET /api/approval-policies/`

List approval policies. Typically admin/manager only.

**Permissions**: `IsAdminOrManager`

**Query params**:
- `resource_type` — filter by transaction type
- `is_active` — true/false

**Response (200 OK)**:
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "PO Approval — High Value",
      "resource_type": "purchase_order",
      "min_amount": 5000000,
      "max_amount": null,
      "auto_approve_if_under": 500000,
      "approval_levels": [
        {"level": 1, "role": "manager", "min_approvers": 1, "description": "Manager review"},
        {"level": 2, "role": "admin", "min_approvers": 1, "description": "Admin sign-off"}
      ],
      "is_active": true
    }
  ]
}
```

---

### `POST /api/approval-policies/`

Create approval policy.

**Permissions**: `IsAdmin`

**Request body**:
```json
{
  "name": "Payroll Approval — All Runs",
  "resource_type": "payroll_run",
  "min_amount": null,
  "max_amount": null,
  "auto_approve_if_under": null,
  "approval_levels": [
    {"level": 1, "role": "manager", "min_approvers": 1, "description": "Manager review"},
    {"level": 2, "role": "admin", "min_approvers": 1, "description": "CEO sign-off"}
  ]
}
```

---

### `PATCH /api/approval-policies/{id}/`

Update policy.

**Permissions**: `IsAdmin`

---

## Integration Points (Hooks into existing apps)

### 1. PurchaseOrder (in `inventory/views.py`)

When PO is submitted (`POST /api/purchase-orders/{id}/submit/`):

```python
def submit_purchase_order(self, request, pk=None):
    po = self.get_object()
    
    # Calculate total
    total = sum(item.line_total for item in po.items.all())
    
    # Find matching approval policy
    policy = ApprovalPolicy.objects.filter(
        resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
        is_active=True
    ).first()  # or match by amount range
    
    if policy and policy.should_auto_approve(total):
        # Auto-approve; no workflow
        po.status = 'submitted'
        po.save()
        return Response({'status': 'auto_approved'})
    
    if policy:
        # Create approval request
        approval_request = ApprovalRequest.objects.create(
            policy=policy,
            resource_type='purchase_order',
            resource_id=po.id,
            requested_by_id=request.user.id,
            amount=total,
            approval_chain_state=policy.approval_levels,
        )
        # Send notification: "PO #{po_number} awaiting manager approval"
        notify_approvers(approval_request, level=1)
        po.status = 'pending_approval'
        po.approval_request_id = approval_request.id
        po.save()
        return Response({'status': 'pending_approval', 'approval_id': approval_request.id})
    
    # No policy; auto-approve
    po.status = 'submitted'
    po.save()
    return Response({'status': 'submitted'})
```

**PurchaseOrder model changes**:
- Add `approval_request = ForeignKey(ApprovalRequest, null=True, blank=True)`
- Add status: `pending_approval` (intermediate state before `submitted`)

---

### 2. LeaveRequest (in `hr/views.py`)

When leave request is created (`POST /api/leave-requests/`):

```python
def create_leave_request(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    leave_request = serializer.save()
    
    # Find policy matching this leave type
    policy = ApprovalPolicy.objects.filter(
        resource_type='leave_request',
        is_active=True
    ).first()
    
    if policy:
        approval = ApprovalRequest.objects.create(
            policy=policy,
            resource_type='leave_request',
            resource_id=leave_request.id,
            requested_by_id=request.user.id,
            approval_chain_state=policy.approval_levels,
        )
        leave_request.status = 'pending_approval'
        leave_request.approval_request_id = approval.id
        leave_request.save()
        notify_approvers(approval, level=1)
    else:
        # Auto-approve
        leave_request.status = 'approved'
        leave_request.save()
    
    return Response(LeaveRequestSerializer(leave_request).data, status=201)
```

---

### 3. PayrollPeriod (in `hr/views.py`)

When payroll is submitted for processing (`POST /api/payroll-periods/{id}/process/`):

```python
def process_payroll(self, request, pk=None):
    period = self.get_object()
    
    # Calculate total salary cost
    total_payroll = PaySlip.objects.filter(payroll_period=period).aggregate(
        total=Sum('gross_salary')
    )['total'] or Decimal('0')
    
    policy = ApprovalPolicy.objects.filter(
        resource_type='payroll_run',
        is_active=True
    ).first()
    
    if policy and policy.should_auto_approve(total_payroll):
        period.status = 'processing'
        period.save()
        return Response({'status': 'processing'})
    
    if policy:
        approval = ApprovalRequest.objects.create(
            policy=policy,
            resource_type='payroll_run',
            resource_id=period.id,
            requested_by_id=request.user.id,
            amount=total_payroll,
            approval_chain_state=policy.approval_levels,
        )
        period.status = 'pending_approval'
        period.approval_request_id = approval.id
        period.save()
        notify_approvers(approval, level=1)
        return Response({'status': 'pending_approval', 'approval_id': approval.id})
    
    period.status = 'processing'
    period.save()
    return Response({'status': 'processing'})
```

---

### 4. CashRequisition (new endpoint in `finance/`)

```python
# In finance/views.py
class CashRequisitionViewSet(viewsets.ModelViewSet):
    queryset = CashRequisition.objects.all()
    serializer_class = CashRequisitionSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        requisition = serializer.save(requested_by_id=self.request.user.id)
        
        # Generate requisition number
        requisition.requisition_number = self._generate_requisition_number()
        requisition.save()
        
        # Create approval
        policy = ApprovalPolicy.objects.filter(
            resource_type='cash_requisition',
            is_active=True
        ).first()
        
        if policy:
            approval = ApprovalRequest.objects.create(
                policy=policy,
                resource_type='cash_requisition',
                resource_id=requisition.id,
                requested_by_id=self.request.user.id,
                amount=requisition.amount,
                approval_chain_state=policy.approval_levels,
            )
            requisition.approval_request_id = approval.id
            requisition.status = 'pending'
            requisition.save()
            notify_approvers(approval, level=1)
```

---

## Notification Integration

When approval action is taken, send notification via `notifications` app:

```python
def notify_approvers(approval_request: ApprovalRequest, level: int):
    """Send notification to pending approvers at a level."""
    from notifications.models import Notification
    
    level_data = next(l for l in approval_request.approval_chain_state if l['level'] == level)
    approver_ids = approval_request.get_approvers_at_level(level)
    
    for approver_id in approver_ids:
        Notification.objects.create(
            recipient_id=approver_id,
            notification_type='approval_request',
            title=f"Action Required: {approval_request.get_resource_type_display()}",
            message=f"{approval_request.get_resource_type_display()} #{approval_request.resource_id} needs your approval (Level {level})",
            resource_type=approval_request.resource_type,
            resource_id=approval_request.resource_id,
            is_read=False,
        )
```

---

## Security & Validation

1. **Role-based approval**: Only users with the required role can approve at a level
2. **Single approval per user per level**: A user can only approve once at a level
3. **Immutable actions**: Once an action is recorded, it cannot be deleted/modified
4. **Audit trail**: All actions timestamped and tied to actor ID
5. **Cross-resource isolation**: ApprovalRequest unique on (resource_type, resource_id)
6. **Amount validation**: Policy amounts validated before workflow creation

---

## Tests (~40 test cases)

### Location: `approvals/tests.py`

#### ApprovalPolicy Tests
- [ ] `test_create_policy_with_approval_levels` — valid JSON structure
- [ ] `test_policy_validation_max_greater_than_min` — validation
- [ ] `test_matches_amount_true_within_range` — amount matching
- [ ] `test_matches_amount_false_below_min` — amount matching
- [ ] `test_should_auto_approve_true_under_threshold` — auto-approve logic
- [ ] `test_should_auto_approve_false_over_threshold` — auto-approve logic

#### ApprovalRequest Tests
- [ ] `test_create_approval_request_pending` — initial status pending
- [ ] `test_unique_per_resource` — only one approval per resource
- [ ] `test_pending_level_returns_current_level` — logic correct
- [ ] `test_all_levels_approved_true_when_done` — validation
- [ ] `test_all_levels_approved_false_pending` — validation
- [ ] `test_get_approvers_at_level_returns_user_ids` — approver resolution

#### ApprovalAction Tests
- [ ] `test_create_approval_action` — action recorded
- [ ] `test_action_immutable` — saved without modification
- [ ] `test_action_by_level_tracked` — level stored

#### ApprovalRequest Workflow Tests
- [ ] `test_single_level_approval_completes_request` — one-step approval
- [ ] `test_two_level_approval_waits_for_second` — multi-level flow
- [ ] `test_rejection_terminates_workflow` — rejection logic
- [ ] `test_approval_chain_state_updated_on_action` — state tracking
- [ ] `test_resolved_at_timestamp_set_on_completion` — timestamp logic
- [ ] `test_cannot_approve_already_resolved_request` — state guard

#### Integration Tests
- [ ] `test_purchase_order_submit_creates_approval` — hook works
- [ ] `test_po_auto_approved_if_under_threshold` — auto-approval in hook
- [ ] `test_po_pending_approval_status_set` — status transition
- [ ] `test_leave_request_creates_approval` — hook works
- [ ] `test_payroll_period_creates_approval` — hook works
- [ ] `test_cash_requisition_creates_approval` — hook works
- [ ] `test_approval_completion_updates_resource_status` — signal/callback

#### Endpoint Tests
- [ ] `test_list_approvals_for_current_user` — GET /api/approvals/ filters correctly
- [ ] `test_list_approvals_filter_by_status` — status filter works
- [ ] `test_list_approvals_filter_by_resource_type` — resource_type filter works
- [ ] `test_approval_detail_includes_all_actions` — GET /api/approvals/{id}/ complete
- [ ] `test_approve_action_increments_count` — POST /api/approvals/{id}/approve/
- [ ] `test_approve_action_moves_to_next_level` — chain progression
- [ ] `test_approve_action_completes_on_final_level` — final approval
- [ ] `test_reject_action_terminates_workflow` — POST /api/approvals/{id}/reject/
- [ ] `test_approve_without_required_role_403` — permission check
- [ ] `test_approve_already_done_by_user_400` — duplicate prevention
- [ ] `test_create_policy_admin_only` — permission check
- [ ] `test_list_policies_manager_and_above` — permission check

---

## Quality Checklist

- [ ] All models have `__str__`, `ordering`, `Meta.indexes`
- [ ] Serializers created for all models (separate Create/Read if needed)
- [ ] ViewSets use `get_serializer_class()` for action-based switching
- [ ] All DecimalField values use `Decimal()` not float
- [ ] All timestamps use `timezone.now()`
- [ ] JSON validation on `approval_levels` field
- [ ] Unique constraint on (resource_type, resource_id)
- [ ] All endpoints secured with permission classes
- [ ] 40+ tests passing
- [ ] Security review completed
- [ ] Integration hooks implemented in PO, Leave, Payroll
- [ ] Notifications sent on approval events
- [ ] Documentation created: `docs/modules/approvals.md`

---

## Traps to Avoid

1. **JSON validation**: `approval_levels` must be validated on save; don't trust structure blindly
2. **Cross-schema FKs**: User IDs stored as IntegerField, not FK; query with direct ID lookup
3. **Duplicate approvals**: Check if action already exists for (approval_request, actor, level) before allowing
4. **State consistency**: When approval is accepted, update resource status AND approval request status in single transaction
5. **Notification timing**: Send before or after saving? Recommend after, in signal handler
6. **Multi-level progression**: After approval, immediately check if next level approvers exist; notify them
7. **Rejected workflow**: When rejected, mark original resource as rejected too (e.g., PO status = 'rejected')

---

## Files Modified/Created

**New**:
- `backend/approvals/models.py` — 3 models (ApprovalPolicy, ApprovalRequest, ApprovalAction)
- `backend/approvals/serializers.py`
- `backend/approvals/views.py`
- `backend/approvals/urls.py`
- `backend/approvals/tests.py`
- `backend/approvals/admin.py`

**Modified**:
- `backend/inventory/models.py` — add `approval_request` FK to PurchaseOrder; add `pending_approval` status
- `backend/inventory/views.py` — add hook in `submit()` action
- `backend/hr/models.py` — add `approval_request` FK to LeaveRequest, PayrollPeriod; add CashRequisition model
- `backend/hr/views.py` — add hooks in create/submit actions
- `backend/finance/models.py` — move/add CashRequisition here (or in hr)
- `backend/config/settings.py` — add `'approvals'` to TENANT_APPS
- `docs/modules/approvals.md` — documentation

---

## Delivery Checklist

[ ] All models implemented with migrations  
[ ] All endpoints tested and secured  
[ ] Integration hooks working (PO, Leave, Payroll, Requisition)  
[ ] 40+ tests passing  
[ ] Notification integration complete  
[ ] Security review passed  
[ ] Documentation complete  
