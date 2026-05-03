from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone

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
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['assigned_to_id', 'status']),
        ]

    def __str__(self):
        return f"{self.project.project_number} — {self.title}"


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
