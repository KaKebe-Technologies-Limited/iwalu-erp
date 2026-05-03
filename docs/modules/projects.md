# Project Management Module

The Project Management module provides a comprehensive system for managing the full lifecycle of business projects, including budget tracking, task management, expense logging, and time entries.

## Data Model
- **Project**: Represents a business initiative with a budget, timeline, and approval status.
- **ProjectTask**: Individual tasks assigned to staff within a project.
- **ProjectExpense**: Expenses incurred against a project, updating the project's actual cost atomically.
- **ProjectTimeEntry**: Time logged by staff members for specific project tasks.

## Approval Workflow
Projects exceeding the `project_approval_threshold` defined in `SystemConfig` require approval through the `approvals` module. When submitted, the project status changes to `pending_approval` until fully approved.

## Integration
- **Approvals**: Integrated for large-budget projects.
- **Finance/HR**: References to users (staff, managers) are managed via `IntegerField(user_id)` to remain tenant-schema safe.

## Endpoints
- `GET /api/projects/`: List/Filter/Search projects.
- `POST /api/projects/`: Create a new draft project.
- `POST /api/projects/{id}/submit/`: Submit project for activation/approval.
- `GET /api/projects/{id}/profitability/`: Retrieve budget vs. actual cost report.
- `POST /api/projects/{id}/tasks/`: Create a new task.
- `POST /api/projects/{id}/expenses/`: Log an expense (atomically updates project cost).
- `POST /api/projects/{id}/time-entries/`: Log time spent on a project/task.
