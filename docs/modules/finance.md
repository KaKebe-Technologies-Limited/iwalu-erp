# Finance Module

## Overview
Double-entry accounting system providing chart of accounts, journal entries, automated transaction recording from sales/purchases/payroll, and financial reporting (trial balance, P&L, balance sheet).

## Models

### Account (Chart of Accounts)
- `code` — unique account code (e.g., "1000", "4000")
- `name` — account name
- `account_type` — asset, liability, equity, revenue, expense
- `parent` — self-referencing FK for tree structure
- `is_system` — prevents deletion of seeded accounts
- `outlet` — optional outlet-level scoping (NULL = company-level)

### FiscalPeriod
- Monthly accounting periods for closing and reporting
- Auto-created when journal entries target a date with no existing period
- `is_closed` — prevents new entries in closed periods

### JournalEntry
- Transaction header with entry_number (JE-YYYYMMDD-NNNN)
- Status workflow: draft → posted → voided
- Source tracking: manual, sale, void_sale, purchase, payroll, transfer
- Generic reference (reference_type + reference_id) to source record

### JournalEntryLine
- Individual debit/credit lines within a journal entry
- Separate debit and credit fields (standard accounting format)
- Links to Account and optional Outlet for segmented reporting

## API Endpoints

### Chart of Accounts
```
GET    /api/accounts/                          List (filter: account_type, is_active, root)
POST   /api/accounts/                          Create (accountant/admin/manager)
GET    /api/accounts/{id}/                     Retrieve
PATCH  /api/accounts/{id}/                     Update
DELETE /api/accounts/{id}/                     Delete (non-system, no journal lines)
```

### Fiscal Periods
```
GET    /api/fiscal-periods/                    List
POST   /api/fiscal-periods/                    Create (accountant/admin/manager)
PATCH  /api/fiscal-periods/{id}/               Update
POST   /api/fiscal-periods/{id}/close/         Close period
```

### Journal Entries
```
GET    /api/journal-entries/                   List (filter: status, source, date_from, date_to)
POST   /api/journal-entries/                   Create with lines (draft)
GET    /api/journal-entries/{id}/              Retrieve with lines
PATCH  /api/journal-entries/{id}/              Update (draft only)
DELETE /api/journal-entries/{id}/              Delete (draft only)
POST   /api/journal-entries/{id}/post/         Post entry (validates balanced)
POST   /api/journal-entries/{id}/void/         Void (creates reversal)
```

### Financial Reports
```
GET    /api/finance/trial-balance/             ?as_of_date=&outlet=
GET    /api/finance/profit-loss/               ?date_from=&date_to=&outlet=
GET    /api/finance/balance-sheet/             ?as_of_date=&outlet=
GET    /api/finance/account-ledger/{id}/       ?date_from=&date_to=
```

## Automated Journal Entries

### Sale Completed
```
DR  Cash/Bank/Mobile Money    (per payment method)
    CR  Sales Revenue         (subtotal - discounts)
    CR  VAT Payable           (tax_total)
```

### Sale Voided
Reversal of the original sale journal entry (DR/CR swapped).

### Purchase Order Received
```
DR  Inventory                 (received cost)
    CR  Accounts Payable      (received cost)
```

### Payroll Approved
```
DR  Salary Expense            (total gross)
DR  NSSF Employer (10%)       (employer contribution)
    CR  NSSF Payable          (employee + employer)
    CR  PAYE Payable          (income tax)
    CR  Net Salary Payable    (total net)
```

## Seed Data
Run `python manage.py seed_chart_of_accounts` to create 20 default system accounts covering assets (1xxx), liabilities (2xxx), equity (3xxx), revenue (4xxx), and expenses (5xxx).

## Permissions
- Read: Any authenticated user
- Write (accounts, entries, periods): IsAccountantOrAbove (admin, manager, accountant)
- Financial reports: Any authenticated user

## Test Coverage
- 15 tests covering: account CRUD, permission checks, balanced entry validation, post/void workflow, account balance calculation, trial balance, P&L, balance sheet
