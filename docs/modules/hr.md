# HR Module

## Overview
Human resources management covering employee records, department management, leave tracking, attendance (clock-in/out), and payroll processing with Uganda-specific tax calculations (PAYE and NSSF).

## Models

### Department
- Name, description, optional outlet assignment
- Active/inactive status

### Employee
- Links to User via `user_id` (IntegerField, cross-schema pattern)
- Auto-generated employee_number (EMP-NNNN)
- Employment details: type (full/part/contract/intern), status (active/on_leave/suspended/terminated)
- Salary and payment info: basic_salary, bank details, mobile money number
- Uganda compliance: NSSF number, TIN number
- Emergency contact information

### LeaveType
- Configurable leave categories (Annual, Sick, Maternity, etc.)
- days_per_year entitlement, is_paid flag

### LeaveBalance
- Per-employee, per-leave-type, per-year tracking
- entitled_days, used_days, carried_over
- remaining_days computed property

### LeaveRequest
- Status workflow: pending → approved/rejected/cancelled
- Approval deducts from LeaveBalance
- Cancellation restricted to own pending requests

### Attendance
- Daily clock-in/clock-out per employee
- hours_worked computed property
- One record per employee per day (unique constraint)

### PayrollPeriod
- Status workflow: draft → processing → approved → paid
- Processing generates PaySlips for all active employees
- Approval creates journal entry in finance module
- Tracks total_gross, total_deductions, total_net

### PaySlip / PaySlipLine
- Per-employee breakdown within a payroll period
- Lines categorized as earning or deduction
- Includes NSSF employee contribution and PAYE

## API Endpoints

### Departments
```
CRUD   /api/departments/                       (admin/manager write, all read)
```

### Employees
```
GET    /api/employees/                         List (filter: department, outlet, status)
POST   /api/employees/                         Create (admin/manager)
GET    /api/employees/{id}/                    Retrieve
PATCH  /api/employees/{id}/                    Update
POST   /api/employees/{id}/terminate/          Terminate employee
```

### Leave
```
CRUD   /api/leave-types/                       Leave type config (admin/manager)
GET    /api/leave-balances/                    List (filter: employee, year)
GET    /api/leave-requests/                    List (filter: employee, status)
POST   /api/leave-requests/                    Submit (auto-resolves employee from user)
POST   /api/leave-requests/{id}/approve/       Approve (admin/manager)
POST   /api/leave-requests/{id}/reject/        Reject with reason (admin/manager)
POST   /api/leave-requests/{id}/cancel/        Cancel own pending request
```

### Attendance
```
GET    /api/attendance/                        List (filter: employee, outlet, date_from, date_to)
POST   /api/attendance/clock-in/               Clock in (self)
POST   /api/attendance/clock-out/              Clock out (self)
GET    /api/attendance/my-today/               Current user's today record
```

### Payroll
```
GET    /api/payroll-periods/                   List
POST   /api/payroll-periods/                   Create (admin/manager)
GET    /api/payroll-periods/{id}/              Detail with all pay slips
POST   /api/payroll-periods/{id}/process/      Generate pay slips
POST   /api/payroll-periods/{id}/approve/      Approve + create journal entry
GET    /api/pay-slips/                         List (filter: employee, payroll_period)
GET    /api/pay-slips/{id}/                    Detail with line items
```

## Uganda Tax Calculations

### PAYE (Monthly Brackets)
| Income Range (UGX)     | Rate |
|------------------------|------|
| 0 – 235,000            | 0%   |
| 235,001 – 335,000      | 10%  |
| 335,001 – 410,000      | 20%  |
| 410,001 – 10,000,000   | 30%  |
| Above 10,000,000       | 40%  |

### NSSF
- Employee contribution: 5% of gross salary
- Employer contribution: 10% of gross salary

## Permissions
- Department/Employee CRUD: IsAdminOrManager
- Leave request submission: IsAuthenticated (any user for self)
- Leave approval/rejection: IsAdminOrManager
- Attendance clock-in/out: IsAuthenticated (any user for self)
- Payroll create/process/approve: IsAdminOrManager

## Test Coverage
- 11 tests covering: department CRUD, permission checks, employee creation with auto-number, termination, leave submit/approve workflow with balance deduction, clock-in/out with duplicate prevention, PAYE bracket calculations, NSSF calculations, payroll process and approve with journal entry creation
