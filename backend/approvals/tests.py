from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from users.models import User
from .models import ApprovalPolicy, ApprovalRequest, ApprovalAction
from inventory.models import PurchaseOrder, Supplier
from outlets.models import Outlet

class ApprovalWorkflowTests(TenantTestCase):
    def setUp(self):
        super().setUp()
        # Create a tenant admin and manager
        self.admin_user = User.objects.create_user(
            username='admin', email='admin@test.com', password='password123', role='admin'
        )
        self.manager_user = User.objects.create_user(
            username='manager', email='manager@test.com', password='password123', role='manager'
        )
        self.clerk_user = User.objects.create_user(
            username='clerk', email='clerk@test.com', password='password123', role='clerk'
        )

        # Create an outlet
        self.outlet = Outlet.objects.create(name="Test Outlet")
        
        # Create a supplier
        self.supplier = Supplier.objects.create(name="Test Supplier")

        # Create a policy for POs > 1M
        self.policy = ApprovalPolicy.objects.create(
            name="PO Approval Policy",
            resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
            min_amount=Decimal('1000000'),
            approval_levels=[
                {"level": 1, "role": "manager", "min_approvers": 1, "description": "Manager Review"},
                {"level": 2, "role": "admin", "min_approvers": 1, "description": "Admin Sign-off"}
            ]
        )

    def test_po_approval_trigger(self):
        # Create a PO that should trigger approval
        po = PurchaseOrder.objects.create(
            po_number="PO-001",
            supplier=self.supplier,
            outlet=self.outlet,
            ordered_by=self.clerk_user.id,
            total_cost=Decimal('1500000')
        )
        
        # Manually trigger submit logic (usually in viewset)
        # Here we test if policy correctly identifies matching
        self.assertTrue(self.policy.matches_amount(po.total_cost))
        
        # Create request
        approval_request = ApprovalRequest.objects.create(
            policy=self.policy,
            resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
            resource_id=po.id,
            requested_by_id=self.clerk_user.id,
            amount=po.total_cost,
            approval_chain_state=self.policy.approval_levels
        )
        
        self.assertEqual(approval_request.status, ApprovalRequest.Status.PENDING)
        self.assertEqual(approval_request.pending_level, 1)

    def test_multi_level_approval(self):
        po = PurchaseOrder.objects.create(
            po_number="PO-002",
            supplier=self.supplier,
            outlet=self.outlet,
            ordered_by=self.clerk_user.id,
            total_cost=Decimal('2000000')
        )
        
        request = ApprovalRequest.objects.create(
            policy=self.policy,
            resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
            resource_id=po.id,
            requested_by_id=self.clerk_user.id,
            amount=po.total_cost,
            approval_chain_state=self.policy.approval_levels
        )

        # Level 1 Approval (Manager)
        level_data = next(l for l in request.approval_chain_state if l['level'] == 1)
        ApprovalAction.objects.create(
            approval_request=request,
            actor_id=self.manager_user.id,
            level=1,
            action=ApprovalAction.Action.APPROVED
        )
        level_data['approved_count'] = 1
        request.save()
        
        self.assertEqual(request.pending_level, 2)
        self.assertEqual(request.status, ApprovalRequest.Status.PENDING)

        # Level 2 Approval (Admin)
        level_data = next(l for l in request.approval_chain_state if l['level'] == 2)
        ApprovalAction.objects.create(
            approval_request=request,
            actor_id=self.admin_user.id,
            level=2,
            action=ApprovalAction.Action.APPROVED
        )
        level_data['approved_count'] = 1
        request.save()
        
        if request.all_levels_approved():
            request.status = ApprovalRequest.Status.APPROVED
            request.resolved_at = timezone.now()
            request.save()

        self.assertEqual(request.status, ApprovalRequest.Status.APPROVED)
        self.assertIsNotNone(request.resolved_at)

    def test_rejection(self):
        po = PurchaseOrder.objects.create(
            po_number="PO-003",
            supplier=self.supplier,
            outlet=self.outlet,
            ordered_by=self.clerk_user.id,
            total_cost=Decimal('2000000')
        )
        
        request = ApprovalRequest.objects.create(
            policy=self.policy,
            resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
            resource_id=po.id,
            requested_by_id=self.clerk_user.id,
            amount=po.total_cost,
            approval_chain_state=self.policy.approval_levels
        )

        # Rejection at Level 1
        ApprovalAction.objects.create(
            approval_request=request,
            actor_id=self.manager_user.id,
            level=1,
            action=ApprovalAction.Action.REJECTED,
            comment="Too expensive"
        )
        request.status = ApprovalRequest.Status.REJECTED
        request.resolved_at = timezone.now()
        request.save()
        
        self.assertEqual(request.status, ApprovalRequest.Status.REJECTED)
        self.assertEqual(request.actions.count(), 1)

    def test_auto_approval(self):
        # Create a policy with auto-approve under 500k
        auto_policy = ApprovalPolicy.objects.create(
            name="Low Value Auto Approve",
            resource_type=ApprovalPolicy.ResourceType.PURCHASE_ORDER,
            auto_approve_if_under=Decimal('500000'),
            approval_levels=[{"level": 1, "role": "manager", "min_approvers": 1}]
        )
        
        self.assertTrue(auto_policy.should_auto_approve(Decimal('400000')))
        self.assertFalse(auto_policy.should_auto_approve(Decimal('600000')))

    def test_po_submission_integration(self):
        from django_tenants.test.client import TenantClient
        client = TenantClient(self.tenant)
        client.force_login(self.manager_user) # Needs to be admin/manager to submit
        
        po = PurchaseOrder.objects.create(
            po_number="PO-INT-001",
            supplier=self.supplier,
            outlet=self.outlet,
            ordered_by=self.manager_user.id,
            total_cost=Decimal('1500000'),
            status='draft'
        )
        
        response = client.post(f'/api/purchase-orders/{po.id}/submit/')
        self.assertEqual(response.status_code, 200)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'pending_approval')
        self.assertIsNotNone(po.approval_request)
        
        approval_request = po.approval_request
        self.assertEqual(approval_request.status, ApprovalRequest.Status.PENDING)
        self.assertEqual(approval_request.amount, po.total_cost)

    def test_leave_request_integration(self):
        from hr.models import Employee, LeaveType
        from django_tenants.test.client import TenantClient
        
        # Setup employee for clerk
        employee = Employee.objects.create(
            user_id=self.clerk_user.id,
            employee_number="EMP-001",
            date_hired=timezone.now().date()
        )
        
        leave_type = LeaveType.objects.create(name="Annual Leave", days_per_year=20)
        
        # Create policy for leave
        LeavePolicy = ApprovalPolicy.objects.create(
            name="Leave Policy",
            resource_type=ApprovalPolicy.ResourceType.LEAVE_REQUEST,
            approval_levels=[{"level": 1, "role": "manager", "min_approvers": 1}]
        )
        
        client = TenantClient(self.tenant)
        client.force_login(self.clerk_user)
        
        response = client.post('/api/leave-requests/', {
            'leave_type': leave_type.id,
            'start_date': timezone.now().date() + timezone.timedelta(days=1),
            'end_date': timezone.now().date() + timezone.timedelta(days=2),
            'days_requested': 1,
            'reason': 'Vacation'
        })
        
        self.assertEqual(response.status_code, 201)
        
        from hr.models import LeaveRequest
        lr = LeaveRequest.objects.get(id=response.data['id'])
        self.assertEqual(lr.status, 'pending_approval')
        self.assertIsNotNone(lr.approval_request)
