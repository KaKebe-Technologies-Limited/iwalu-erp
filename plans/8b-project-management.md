# Phase 8b Implementation Plan: Project Management

**Backend only** (tenant-scoped, new `projects` app)
**Estimated scope**: 4 models, 10 endpoints, ~40 tests, approval workflow integration
**New apps**: `projects` (tenant-scoped)
**Tenant-scoped**: Yes

---

## Overview

Implements full project lifecycle management:
1. **Projects**: Budget, dates, status, manager assignment
2. **Tasks**: Assigned to staff with priority, deadline, and status tracking
3. **Expenses**: Logged against projects; updates `actual_cost` atomically
4. **Time tracking**: Hours per staff member per project/task
5. **Approval integration**: High-budget projects trigger approval workflow
6. **Profitability reports**: Budget vs actual cost summary

Integrates with `approvals` (budget threshold), `hr` (employee IDs), and optionally `finance` (journal entries for expenses).

---

## Models

### `Project` (in `projects/models.py`)

```python
class Project(models.Model):
    """
    A business project with budget, timeline, and task tracking.
    Budget-exceeding projects require approval before becoming active.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_APPROVAL = 'pending_approval', 'Pending Approval'
        ACTIVE = 'active', 'Active'
        ON_HOLD = 'on_hold', 'On Hold'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    project_number = models.CharField(
        max_length=30, unique=True,
        help_text='Auto-generated: PRJ-YYYYMMDD-XXXX'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Status lifecycle
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    # Manager (cross-schema safe: IntegerField)
    manager_id = models.IntegerField(help_text='User ID of project manager')

    # Timeline
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Budget
    budget = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Approved project budget (UGX)'
    )
    actual_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Running total of logged expenses'
    )

    # Approval integration
    approval_request = models.ForeignKey(
        'approvals.ApprovalRequest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projects'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'manager_id']),
        ]

    def __str__(self):
        return f"{self.project_number} - {self.name}"

    @property
    def budget_remaining(self) -> Decimal:
        return self.budget - self.actual_cost

    @property
    def is_over_budget(self) -> bool:
        return self.actual_cost > self.budget

    @property
    def budget_utilisation_pct(self) -> Decimal:
        if self.budget == 0:
            return Decimal('0')
        return (self.actual_cost / self.budget * 100).quantize(Decimal('0.01'))
```

---

### `ProjectTask` (in `projects/models.py`)

```python
class ProjectTask(models.Model):
    """
    An individual task within a project.
    Assigned to a staff member. Time entries link back to tasks.
    """
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        BLOCKED = 'blocked', 'Blocked'
        DONE = 'done', 'Done'
        CANCELLED = 'cancelled', 'Cancelled'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Assignment (cross-schema safe)
    assigned_to_id = models.IntegerField(
        null=True, blank=True,
        help_text='Employee ID assigned to this task'
    )
    created_by_id = models.IntegerField(help_text='User who created the task')

    # Status & priority
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.TODO
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )

    # Timeline
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'due_date']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['assigned_to_id', 'status']),
        ]

    def __str__(self):
        return f"{self.project.project_number} — {self.title}"
```

---

### `ProjectExpense` (in `projects/models.py`)

```python
class ProjectExpense(models.Model):
    """
    An expense charged to a project. Creating or deleting an expense
    updates project.actual_cost atomically.
    """
    class Category(models.TextChoices):
        LABOUR = 'labour', 'Labour'
        MATERIALS = 'materials', 'Materials'
        EQUIPMENT = 'equipment', 'Equipment Hire'
        SUBCONTRACT = 'subcontract', 'Subcontract'
        TRAVEL = 'travel', 'Travel & Transport'
        OTHER = 'other', 'Other'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='expenses'
    )
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=15, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Expense amount (UGX)'
    )
    expense_date = models.DateField()

    # Staff who incurred the expense (cross-schema safe)
    incurred_by_id = models.IntegerField(help_text='User ID who incurred the expense')
    approved_by_id = models.IntegerField(
        null=True, blank=True,
        help_text='User ID who approved the expense'
    )

    receipt_number = models.CharField(max_length=100, blank=True)

    # Optional finance integration
    journal_entry_id = models.IntegerField(
        null=True, blank=True,
        help_text='JournalEntry ID if expense was journalised to GL'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['project', 'expense_date']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.project.project_number} — {self.description} (UGX {self.amount})"
```

---

### `ProjectTimeEntry` (in `projects/models.py`)

```python
class ProjectTimeEntry(models.Model):
    """
    Hours logged by a staff member against a project (and optionally a task).
    unique_together prevents double-logging for the same staff/date/task.
    """
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='time_entries'
    )
    task = models.ForeignKey(
        ProjectTask, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='time_entries'
    )

    # Staff (cross-schema safe)
    staff_id = models.IntegerField(help_text='User ID of staff member')

    date = models.DateField()
    hours = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.25'))],
        help_text='Hours worked (minimum 0.25 = 15 min)'
    )
    description = models.TextField(
        blank=True,
        help_text='Summary of work done'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        unique_together = ('project', 'staff_id', 'date', 'task')
        indexes = [
            models.Index(fields=['project', 'date']),
            models.Index(fields=['staff_id', 'date']),
        ]

    def __str__(self):
        return f"{self.staff_id} — {self.hours}h on {self.project.project_number} ({self.date})"
```

---

## Endpoints

### `GET /api/projects/`

List projects. Filter by `status`, `manager_id`. Search by `name`, `project_number`.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "count": 12,
  "results": [
    {
      "id": 3,
      "project_number": "PRJ-20260430-0003",
      "name": "Station Canopy Renovation",
      "status": "active",
      "manager_id": 5,
      "start_date": "2026-04-01",
      "end_date": "2026-06-30",
      "budget": "25000000",
      "actual_cost": "8500000",
      "budget_remaining": "16500000",
      "is_over_budget": false,
      "budget_utilisation_pct": "34.00"
    }
  ]
}
```

---

### `POST /api/projects/`

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "name": "Station Canopy Renovation",
  "description": "Repaint and reinforce main canopy structure",
  "manager_id": 5,
  "start_date": "2026-04-01",
  "end_date": "2026-06-30",
  "budget": "25000000"
}
```

**Logic**:
- Auto-generate `project_number` (PRJ-YYYYMMDD-XXXX sequence)
- Set `status = 'draft'`

**Response (201 Created)**: Full project object.

---

### `POST /api/projects/{id}/submit/`

Submit project for activation. Triggers approval workflow if budget exceeds threshold.

**Permissions**: `IsAdminOrManager`

**Logic**:
1. Project must be in `draft` or `pending_approval` (resubmit) status
2. Check `system_config.SystemConfig` for `project_approval_threshold` setting
3. If `budget >= threshold`:
   - Find active `ApprovalPolicy` with `resource_type='project'`
   - Create `ApprovalRequest`; set `project.approval_request = request`; set `status='pending_approval'`
   - Notify first-level approvers
4. If `budget < threshold` (or no policy): set `status='active'` directly

**Note**: This requires adding `PROJECT = 'project', 'Project'` to `approvals.models.ApprovalPolicy.ResourceType.choices` and creating a new migration for that field change.

**Response (200 OK)**:
```json
{
  "status": "pending_approval",
  "approval_id": 12,
  "message": "Project submitted for approval. Budget exceeds threshold."
}
```
or
```json
{
  "status": "active",
  "message": "Project activated. No approval required."
}
```

---

### `GET /api/projects/{id}/profitability/`

Budget vs cost report for a project.

**Permissions**: `IsAdminOrManager` or `IsAccountant`

**Response (200 OK)**:
```json
{
  "project_number": "PRJ-20260430-0003",
  "name": "Station Canopy Renovation",
  "budget": "25000000",
  "actual_cost": "8500000",
  "budget_remaining": "16500000",
  "is_over_budget": false,
  "budget_utilisation_pct": "34.00",
  "expenses_by_category": {
    "labour": "3000000",
    "materials": "5000000",
    "equipment": "500000",
    "other": "0"
  },
  "total_hours_logged": "240.00",
  "task_summary": {
    "todo": 3,
    "in_progress": 2,
    "done": 5,
    "cancelled": 0
  }
}
```

---

### `GET /api/projects/{id}/tasks/`

List tasks for a project. Filter by `status`, `assigned_to_id`, `priority`.

**Permissions**: `IsAuthenticated`

---

### `POST /api/projects/{id}/tasks/`

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "title": "Source canopy paint suppliers",
  "description": "Get 3 quotes for exterior paint",
  "assigned_to_id": 8,
  "priority": "high",
  "due_date": "2026-04-15"
}
```

---

### `PATCH /api/projects/{id}/tasks/{task_id}/`

Update task status, assignee, or dates.

**Permissions**: `IsAdminOrManager`, or own task (staff can update their own task status)

**Logic**: If `status` is set to `'done'`, auto-set `completed_at = timezone.now()`.

---

### `POST /api/projects/{id}/expenses/`

Log an expense. Atomically increments `project.actual_cost`.

**Permissions**: `IsAuthenticated`

**Request body**:
```json
{
  "description": "Scaffolding hire — week 1",
  "category": "equipment",
  "amount": "500000",
  "expense_date": "2026-04-05",
  "receipt_number": "INV-SCAFFOLD-001"
}
```

**Logic** (inside `transaction.atomic()`):
1. Create `ProjectExpense`
2. `Project.objects.filter(pk=project.pk).update(actual_cost=F('actual_cost') + amount)`

**Response (201 Created)**: Expense object + updated `project.actual_cost`.

---

### `GET /api/projects/{id}/expenses/`

List project expenses. Filter by `category`, `expense_date`.

**Permissions**: `IsAuthenticated`

---

### `POST /api/projects/{id}/time-entries/`

Log time worked on a project.

**Permissions**: `IsAuthenticated`

**Request body**:
```json
{
  "task_id": 7,
  "date": "2026-04-05",
  "hours": "8.00",
  "description": "On-site supervision of scaffolding setup"
}
```

**Logic**: `staff_id` is set from `request.user.id`. Enforce `unique_together` — duplicate returns 400.

---

### `GET /api/projects/{id}/time-entries/`

List time entries for a project. Filter by `staff_id`, `date`.

**Permissions**: `IsAuthenticated`

---

## Approval Integration

### Changes to `approvals` app

Add `PROJECT` to `ApprovalPolicy.ResourceType`:

```python
# approvals/models.py — inside ResourceType
PROJECT = 'project', 'Project'
```

This requires a new migration:
```bash
python manage.py makemigrations approvals --name="add_project_resource_type"
```

Then update the `submit` action to look up the policy by `resource_type='project'`.

---

## Security & Validation

1. **Tenant isolation**: All models tenant-scoped; no cross-tenant access
2. **actual_cost atomicity**: Use `F()` expression in expense creation/deletion — never read-modify-write
3. **Task ownership**: Staff can only update their own tasks' `status` — not reassign, delete, or change priority
4. **Budget validation**: `budget > 0` enforced at model level
5. **Time entry user**: `staff_id` always set from `request.user.id` — not from request body (prevents logging time as someone else)
6. **Expense deletion guard**: If expense is deleted, decrement `actual_cost` atomically via signal or override `destroy()`
7. **Cross-schema FKs**: `manager_id`, `assigned_to_id`, `incurred_by_id`, `staff_id` all `IntegerField`
8. **Approval resource type**: Adding 'project' to choices requires migration — do NOT edit existing data

---

## Tests (~40 test cases)

### Location: `projects/tests.py` — use `TenantTestCase` + `TenantClient`

#### Project Tests
- [ ] `test_create_project_generates_project_number` — PRJ-YYYYMMDD-XXXX format
- [ ] `test_create_project_sets_draft_status` — default status=draft
- [ ] `test_create_project_requires_manager_role` — cashier gets 403
- [ ] `test_budget_remaining_property` — budget - actual_cost
- [ ] `test_is_over_budget_when_exceeded` — actual_cost > budget
- [ ] `test_budget_utilisation_pct_computed` — (actual/budget)*100
- [ ] `test_list_projects_paginated` — paginated results
- [ ] `test_list_projects_filter_by_status` — status filter works
- [ ] `test_get_project_detail` — returns full project object

#### Submit / Approval Tests
- [ ] `test_submit_small_budget_activates_project` — status→active, no approval
- [ ] `test_submit_large_budget_creates_approval_request` — approval created, status→pending_approval
- [ ] `test_submit_no_approval_policy_activates_project` — no policy → auto-active
- [ ] `test_submit_already_active_project_returns_400` — cannot re-submit active
- [ ] `test_submit_requires_manager_role` — cashier forbidden

#### Profitability Tests
- [ ] `test_profitability_endpoint_no_expenses` — budget_remaining = budget, actual_cost=0
- [ ] `test_profitability_expense_breakdown_by_category` — categories summed
- [ ] `test_profitability_total_hours_logged` — hours summed
- [ ] `test_profitability_requires_manager_or_accountant` — cashier forbidden

#### ProjectTask Tests
- [ ] `test_create_task_under_project` — 201 created
- [ ] `test_task_status_done_sets_completed_at` — completed_at set on status=done
- [ ] `test_staff_can_update_own_task_status` — own task status updatable
- [ ] `test_staff_cannot_update_others_task` — 403 on other's task
- [ ] `test_task_filter_by_status` — filter works
- [ ] `test_task_filter_by_assigned_to` — assignee filter works

#### ProjectExpense Tests
- [ ] `test_create_expense_increments_actual_cost` — project.actual_cost updated
- [ ] `test_delete_expense_decrements_actual_cost` — project.actual_cost decremented
- [ ] `test_expense_amount_must_be_positive` — 0 and negative rejected
- [ ] `test_expense_requires_authentication` — 401 without auth
- [ ] `test_expense_filter_by_category` — category filter works

#### ProjectTimeEntry Tests
- [ ] `test_create_time_entry_logs_hours` — 201 created
- [ ] `test_create_time_entry_staff_id_from_request_user` — cannot log as someone else
- [ ] `test_duplicate_time_entry_returns_400` — unique_together enforced
- [ ] `test_time_entry_minimum_hours_025` — 0.1 hours rejected
- [ ] `test_time_entry_filter_by_date` — date filter works
- [ ] `test_task_set_null_on_task_delete` — time entry retained when task deleted

---

## Quality Checklist

- [ ] All models have `__str__`, `ordering`, `Meta.indexes`
- [ ] `actual_cost` updated via `F()` expression (never read-modify-write)
- [ ] `staff_id` on `ProjectTimeEntry` always set from `request.user.id`
- [ ] Task `completed_at` auto-set when status→done
- [ ] `PROJECT` resource type added to `approvals.ApprovalPolicy.ResourceType` with migration
- [ ] Expense delete decrements `actual_cost` (override `destroy` or use signal)
- [ ] All monetary fields `DecimalField(max_digits=15, decimal_places=2)`
- [ ] Hours field `DecimalField(max_digits=5, decimal_places=2)`, minimum 0.25
- [ ] All user ID fields are `IntegerField`
- [ ] 40+ tests passing
- [ ] Security review completed
- [ ] Documentation: `docs/modules/projects.md`

---

## Traps to Avoid

1. **actual_cost race condition**: Never do `project.actual_cost += amount; project.save()` — use `F('actual_cost') + amount` in `update()` to prevent concurrent write races
2. **Time entry staff from body**: Do not allow `staff_id` to be passed in request body — always use `request.user.id`
3. **Task cascade delete**: `ProjectTimeEntry.task` must be `on_delete=SET_NULL` not `CASCADE` — deleting a task should not delete time history
4. **Approval resource type migration**: Adding 'project' to a `TextChoices` field requires a new migration on the `approvals` app — don't skip this
5. **Missing approval policy**: If no `ApprovalPolicy` exists for 'project', the submit action should default to auto-approve (not crash)
6. **Over-budget does not block**: Being over budget is a warning/reporting state, not a hard block — expenses can still be logged
7. **Expense delete without actual_cost update**: If `ProjectExpense` is deleted (via `destroy` endpoint), `actual_cost` must be decremented atomically

---

## Files to Create

**New**:
- `backend/projects/__init__.py`
- `backend/projects/apps.py`
- `backend/projects/models.py` — 4 models
- `backend/projects/serializers.py`
- `backend/projects/views.py`
- `backend/projects/urls.py`
- `backend/projects/admin.py`
- `backend/projects/tests.py`
- `backend/projects/migrations/0001_initial.py` (via `makemigrations`)

**Modified**:
- `backend/approvals/models.py` — add `PROJECT = 'project', 'Project'` to `ResourceType`
- `backend/approvals/migrations/0002_add_project_resource_type.py` — new migration
- `backend/config/settings.py` — add `'projects'` to `TENANT_APPS`
- `backend/api/urls.py` — add `path('projects/', include('projects.urls'))`

**Documentation**:
- `docs/modules/projects.md`

---

## Delivery Checklist

- [ ] All 4 models implemented with migrations
- [ ] `approvals.ApprovalPolicy.ResourceType` extended with `PROJECT` + migration applied
- [ ] All 10 endpoints implemented and secured
- [ ] `actual_cost` updated atomically on expense create/delete
- [ ] Time entry `staff_id` always from `request.user.id`
- [ ] Approval triggered correctly for large-budget projects
- [ ] 40+ tests passing (`python manage.py test projects`)
- [ ] Security review completed
- [ ] `python manage.py check` — no system errors
- [ ] `python manage.py migrate_schemas` — no errors
- [ ] Documentation: `docs/modules/projects.md`
