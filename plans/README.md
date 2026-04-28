# Phase 7 Implementation Plans

This directory contains detailed, machine-readable implementation plans for Phase 7b, 7c, and 7d of the Nexus ERP backend.

These plans are designed for **Gemini CLI**, **KiloCode**, or other code generation tools to implement with minimal human oversight. After implementation, a human reviewer should audit the work using the security review process documented in each plan.

---

## Plans Included

### 1. **7b-saas-subscription-billing.md** — SaaS Operations & Subscription Billing

**Scope**: Multi-tenant subscription management, billing cycles, invoice generation, tenant suspension/reactivation, resend-verification endpoint, rate limiting.

**Deliverables**:
- 3 models: `SubscriptionPlan`, `TenantSubscription`, `SubscriptionInvoice`
- 9 endpoints (public + authenticated + admin)
- 2 management commands (generate invoices, check overdue subscriptions)
- 50+ test cases
- Email notifications for billing events

**Time Estimate**: 3–4 days (Gemini) or 5–6 days (human)

**Key Files**:
- `tenants/models.py` — add models
- `tenants/serializers.py` — create new
- `tenants/views.py` — create/extend
- `tenants/urls.py` — add billing routes
- `tenants/management/commands/` — 2 commands
- `docs/modules/billing.md` — new documentation

---

### 2. **7c-approval-workflows.md** — Approval Workflows

**Scope**: Multi-level approval chains for POs, leave requests, payroll, cash requisitions. Configurable by amount/role. Integration with existing transaction types.

**Deliverables**:
- 3 models: `ApprovalPolicy`, `ApprovalRequest`, `ApprovalAction`
- 8 endpoints (list, detail, approve, reject, manage policies)
- Integration hooks into `inventory`, `hr`, `finance` apps
- CashRequisition model (new, in `finance` or `hr`)
- 40+ test cases
- Notification integration

**Time Estimate**: 4–5 days (Gemini) or 6–7 days (human)

**Key Files**:
- `approvals/` — new app (models, views, serializers, urls, tests)
- `inventory/models.py` — add `approval_request` FK to PO
- `inventory/views.py` — hook submit() action
- `hr/models.py` — add `approval_request` FK + CashRequisition model
- `hr/views.py` — hooks for leave, payroll
- `finance/models.py` — CashRequisition (or in hr)
- `docs/modules/approvals.md` — new documentation

---

### 3. **7d-asset-management.md** — Asset Management

**Scope**: Fixed asset tracking, depreciation calculation (straight-line, reducing balance), assignment history, maintenance logs, disposal gain/loss, optional finance integration.

**Deliverables**:
- 5 models: `AssetCategory`, `Asset`, `AssetAssignment`, `MaintenanceLog`, `AssetDisposal`
- 8 endpoints (CRUD assets, assign, log maintenance, dispose, depreciation schedule)
- 1 management command (calculate monthly depreciation)
- 35+ test cases
- Optional JournalEntry creation for depreciation

**Time Estimate**: 3–4 days (Gemini) or 4–5 days (human)

**Key Files**:
- `assets/` — new app (models, views, serializers, urls, tests)
- `assets/management/commands/calculate_monthly_depreciation.py` — cron task
- `docs/modules/assets.md` — new documentation

---

## How to Use These Plans

### For Gemini CLI

```bash
# Start with a single plan
gemini code --plan /path/to/plans/7b-saas-subscription-billing.md

# Or ask Gemini to implement all three
gemini code --plan /path/to/plans/7b-saas-subscription-billing.md \
                    --plan /path/to/plans/7c-approval-workflows.md \
                    --plan /path/to/plans/7d-asset-management.md
```

### For KiloCode

Each plan is self-contained and can be read directly into KiloCode's context. Follow the step-by-step phases listed in each plan.

### For Human Review

1. **Read the plan** to understand scope and requirements
2. **Have Gemini/KiloCode implement** it (all phases in order)
3. **Run the quality checklist** at the end of each plan
4. **Run security review** using the `security-reviewer` agent
5. **Verify tests pass**: `docker compose exec backend python manage.py test [app]`
6. **Review endpoints** with curl or Postman to ensure contracts match

---

## Constraints & Quality Gates

### Every Implementation Must Include

✅ **Models**
- All fields with appropriate validators
- `__str__`, `ordering`, and `Meta.indexes` on all models
- Docstrings explaining purpose and lifecycle

✅ **Serializers**
- Separate Create/Read serializers where needed (e.g., no password in Read)
- All fields explicitly listed (no `__all__`)
- Nested serializers for related data

✅ **ViewSets**
- `permission_classes` on every ViewSet
- `get_serializer_class()` for action-based switching
- Custom actions with `@action` decorator where needed
- Proper HTTP status codes (201 Created, 204 No Content, etc.)

✅ **Testing**
- Minimum test count specified in each plan (35–50 tests per app)
- Test happy path AND error cases
- Management command tests for cron tasks
- Integration tests for inter-app hooks

✅ **Security**
- All endpoints checked with `security-reviewer` agent before merge
- Tenant isolation verified (cross-tenant access impossible)
- Permission classes prevent unauthorized access
- Input validation on all user-supplied fields
- No hardcoded secrets; all config in .env or settings.py

✅ **Documentation**
- Docstrings on all models and viewsets
- New `docs/modules/[app].md` file with:
  - Data model diagrams (or ASCII tables)
  - Endpoint reference
  - Configuration guide
  - Integration points
  - Example curl commands

✅ **Migrations**
- Generated with `python manage.py makemigrations`
- Run successfully: `docker compose exec backend python manage.py migrate_schemas`
- No migration errors in any tenant schema

---

## Typical Implementation Order

1. **7b first** (subscription billing) — foundational for SaaS business model
2. **7c second** (approval workflows) — cross-cutting concern affecting multiple existing apps
3. **7d last** (asset management) — standalone, low interdependency

Alternatively, if you have multiple developers:
- **Dev A**: 7b (billing)
- **Dev B**: 7c (approvals) + hook integrations into 7a/7d
- **Dev C**: 7d (assets) + optional finance integration

---

## Testing Checklist for Reviewers

Before approving any implementation:

```bash
# 1. Compile check
docker compose exec backend python manage.py check

# 2. Run all tests for the app
docker compose exec backend python manage.py test [app_name]

# 3. Check for migrations
ls backend/[app_name]/migrations/ | grep -E '^0[0-9]+_'

# 4. Run migrations (safe, testing-only)
docker compose exec backend python manage.py migrate_schemas

# 5. Check admin site works
docker compose exec backend python manage.py createsuperuser  # if needed
# Visit http://localhost:8000/admin/

# 6. Test endpoints with curl (examples in each plan)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/billing/my-subscription/

# 7. Security review
# Use /security-review skill to audit for vulnerabilities
```

---

## Common Gotchas & Traps

### Tenant Isolation
- **DO**: Use `request.tenant` to scope queries
- **DON'T**: Query all records without tenant filtering
- **Trap**: Cross-schema ForeignKeys don't work; use IntegerField instead

### Decimals & Money
- **DO**: Use `Decimal()` for prices, amounts, costs
- **DON'T**: Use float (precision loss)
- **Trap**: `0.1 + 0.2 != 0.3` in float; use Decimal

### Timezones
- **DO**: Use `timezone.now()` for current time
- **DON'T**: Use `datetime.now()` (naive datetime)
- **Trap**: Naive datetimes cause comparison errors

### Testing Tenant Apps
- **DO**: Use `TenantTestCase` + `TenantClient` from django-tenants
- **DON'T**: Use standard Django `TestCase`
- **Trap**: Standard TestCase doesn't create tenant schema; tests fail mysteriously

### Management Commands
- **DO**: Make idempotent (safe to run multiple times)
- **DON'T**: Assume state; verify before modifying
- **Trap**: Running twice creates duplicate data; add guards

---

## After Implementation: Vetting Workflow

Once the developer completes implementation:

1. **Developer** creates a git branch: `feat/phase-7b-billing` (etc.)
2. **Developer** runs `./scripts/pre-submit-check.sh` (or manual equivalent):
   ```bash
   docker compose exec backend python manage.py check
   docker compose exec backend python manage.py test [app]
   docker compose exec backend python manage.py migrate_schemas
   ```
3. **Reviewer** (you) runs:
   ```bash
   /security-review  # or /security-reviewer agent
   ```
4. **Reviewer** checks:
   - All endpoints respond correctly
   - Tenant isolation confirmed
   - Tests all pass
   - No console errors
5. **Reviewer** merges to main and triggers any necessary frontend work

---

## References

- **Django ORM**: https://docs.djangoproject.com/en/5.0/topics/db/models/
- **DRF ViewSets**: https://www.django-rest-framework.org/api-guide/viewsets/
- **django-tenants**: https://django-tenants.readthedocs.io/
- **Project CLAUDE.md**: `backend/CLAUDE.md` for conventions
- **Existing modules**: Reference `finance/`, `hr/`, `inventory/` for patterns

---

## Questions & Issues

If implementation gets stuck:

1. **Check the plan** — re-read the relevant section
2. **Check CLAUDE.md** — project conventions often explain the "why"
3. **Look at existing code** — similar patterns in `finance/`, `hr/`, `inventory/`
4. **Ask for clarification** — the plans are detailed but not exhaustive

---

**Last Updated**: 27 April 2026  
**Plans Created For**: Gemini CLI, KiloCode, or similar code-generation tools  
**Expected Outcome**: Production-ready backend code, fully tested, documented, and secure
