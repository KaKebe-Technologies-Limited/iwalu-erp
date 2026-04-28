# Approval Workflows Module

The Approval Workflows module provides a flexible system for multi-level approvals across different business resources.

## Key Features
- **Configurable Policies**: Define approval chains based on resource type and transaction amount.
- **Multi-level Approvals**: Support for sequential approval levels (e.g., Manager -> Admin).
- **Auto-approval**: Define thresholds below which transactions are automatically approved.
- **Audit Trail**: Complete history of approval actions (approvals/rejections) with comments.
- **Notification Integration**: Auto-notifies potential approvers when their action is required.

## Resources Supported
- Purchase Orders
- Leave Requests
- Payroll Runs
- Cash Requisitions
- Stock Adjustments

## Workflow
1. **Resource Submission**: When a resource (e.g., a Purchase Order) is submitted, the system checks for a matching `ApprovalPolicy`.
2. **Request Creation**: If a policy matches, an `ApprovalRequest` is created, and the resource status is set to `pending_approval`.
3. **Approval Levels**: Approvers at each level must approve the request sequentially.
4. **Resolution**: 
   - If fully approved, the resource status is updated (e.g., to `submitted` or `approved`).
   - If rejected at any level, the workflow terminates, and the resource is marked as `rejected`.

## API Endpoints

### Approval Policies
- `GET /api/approval-policies/`: List policies.
- `POST /api/approval-policies/`: Create a policy (Admin only).
- `PATCH /api/approval-policies/{id}/`: Update a policy (Admin only).

### Approval Requests
- `GET /api/approvals/`: List requests pending action for the current user.
- `GET /api/approvals/{id}/`: Detailed view of a request and its action history.
- `POST /api/approvals/{id}/approve/`: Approve the current level.
- `POST /api/approvals/{id}/reject/`: Reject the request (Comment required).

## Technical Details
- **App Name**: `approvals`
- **Models**: `ApprovalPolicy`, `ApprovalRequest`, `ApprovalAction`
- **Integration**: Hooks into `inventory.PurchaseOrder`, `hr.LeaveRequest`, `hr.PayrollPeriod`, and `finance.CashRequisition`.
- **Permissions**: Respects user roles (`admin`, `manager`, `accountant`, etc.) as defined in policies.
