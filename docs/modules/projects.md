# Project Management Module

The `projects` app provides comprehensive project lifecycle management, including budget tracking, expense management, task organization, and time logging with real-time profitability analysis.

## Models

### Project
Represents a business initiative with budget and timeline.
- `project_number`: Auto-generated unique identifier (PRJ-YYYYMMDD-XXXX).
- `name`: Project name.
- `manager_id`: Project manager (IntegerField for cross-schema safety).
- `start_date`, `end_date`: Project timeline.
- `budget`: Initial budget allocation in UGX.
- `actual_cost`: Computed from expenses using F() arithmetic for atomicity.
- `status`: DRAFT → PENDING_APPROVAL → ACTIVE → (ON_HOLD / COMPLETED / CANCELLED).
- `approval_request`: Reference to approval workflow if over threshold.

### ProjectTask
Individual work items within a project.
- `title`, `description`: Task details.
- `project`: Foreign key to Project.
- `status`: TODO, IN_PROGRESS, DONE, CANCELLED.
- `priority`: HIGH, MEDIUM, LOW.
- `assigned_to_id`: Staff member assigned (IntegerField).
- `due_date`: Target completion date.
- `created_by_id`: Creator (IntegerField).
- `completed_at`: Timestamp when marked DONE.

### ProjectExpense
Recorded spending against the project.
- `project`: Foreign key to Project.
- `description`: Expense details.
- `category`: materials, labor, overhead, other.
- `amount`: Expense amount in UGX.
- `expense_date`: When expense occurred.
- `incurred_by_id`: Who recorded it (IntegerField).
- **On create/update/delete**: Project's `actual_cost` is atomically updated using F() expressions and Greatest() to prevent negatives.

### ProjectTimeEntry
Hours logged against a project.
- `project`: Foreign key to Project.
- `task`: Optional reference to ProjectTask.
- `staff_id`: Who logged the time (IntegerField).
- `date`: When work occurred.
- `hours`: Time spent (DecimalField).
- `description`: What was done.

## Key Workflows

### Project Lifecycle
1. **DRAFT**: Created with initial budget. Can be edited freely.
2. **Submit** → Check if `budget >= project_approval_threshold`:
   - If yes: Create ApprovalRequest, move to PENDING_APPROVAL.
   - If no: Auto-activate to ACTIVE.
3. **ACTIVE**: Expenses logged, tasks tracked. Can be held or completed.
4. **ON_HOLD**: Paused; can resume to ACTIVE.
5. **COMPLETED**: Final status; no further changes.
6. **CANCELLED**: Aborted; can cancel from any state except COMPLETED.

### Expense Management
- **Create**: Expense amount added to project's `actual_cost` via `perform_create()`.
- **Update**: Difference (new - old) added to `actual_cost` via `perform_update()` with F() arithmetic.
- **Delete**: Amount subtracted from `actual_cost` via `perform_destroy()`, floored at 0 with Greatest().

### Profitability Report
`GET /api/projects/{id}/profitability/` returns:
- Budget, actual cost, remaining budget, utilization percentage, over-budget flag.
- Expenses grouped by category.
- Total hours logged.
- Task count by status.

## Approval Integration
Projects exceeding `SystemConfig.project_approval_threshold` require approval via the `approvals` module. The approval policy is configured with per-level approvers and minimum approval counts.

## Permissions
- **Admin/Manager**: Full CRUD, can submit and manage all projects.
- **Accountant**: Read-only access to profitability and expense reports.
- **Others**: Time entry/task updates limited to own entries.

## API Endpoints
- `GET /api/projects/` — List with filtering by status, manager.
- `POST /api/projects/` — Create draft.
- `GET /api/projects/{id}/` — Retrieve with calculations.
- `PATCH /api/projects/{id}/` — Update (manager only).
- `POST /api/projects/{id}/submit/` — Activate or submit for approval.
- `POST /api/projects/{id}/complete/` — Mark as completed.
- `POST /api/projects/{id}/cancel/` — Cancel project.
- `POST /api/projects/{id}/hold/` — Pause active project.
- `POST /api/projects/{id}/resume/` — Resume held project.
- `GET /api/projects/{id}/profitability/` — Budget analysis.
- `GET /api/projects/tasks/` — Task list/filtering.
- `POST /api/projects/tasks/` — Create task.
- `GET /api/projects/expenses/` — Expense list/filtering.
- `POST /api/projects/expenses/` — Log expense.
- `PATCH /api/projects/expenses/{id}/` — Update expense (recalculates cost).
- `DELETE /api/projects/expenses/{id}/` — Remove expense.
- `POST /api/projects/time-entries/` — Log hours.

## Data Validation
- **Date validation**: end_date must be >= start_date.
- **Expense updates**: Project reassignment prevented in `validate_project()`.
- **State transitions**: Only valid status transitions allowed per ALLOWED_TRANSITIONS dict.
