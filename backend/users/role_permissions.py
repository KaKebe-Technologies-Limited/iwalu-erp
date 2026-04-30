"""
Role-to-permission mapping used by the /api/auth/me/permissions/ endpoint.

This is the single source of truth for what each role can see and do in the
dashboard. The frontend uses the returned payload to build the sidebar and
route guards; the backend enforces the same rules at the ViewSet level.

Sections map to sidebar nav items. Actions are fine-grained verbs used by
frontend feature gates (e.g. showing/hiding "Void sale" buttons).

When updating this file, also audit the corresponding ViewSets in
outlets/sales/products/inventory/finance/hr/fuel/notifications/system_config
to make sure the ViewSet permission_classes match.
"""


# All dashboard sections available in the sidebar
ALL_SECTIONS = [
    'dashboard',
    'pos',
    'sales',
    'shifts',
    'products',
    'discounts',
    'inventory',
    'outlets',
    'employees',
    'fuel',
    'accounting',
    'reports',
    'notifications',
    'settings',
]

# All fine-grained actions a user might perform
ALL_ACTIONS = [
    'open_shift',
    'close_shift',
    'process_sale',
    'void_sale',
    'manage_products',
    'adjust_stock',
    'manage_discounts',
    'manage_outlets',
    'manage_employees',
    'manage_fuel_pumps',
    'manage_fuel_deliveries',
    'confirm_reconciliation',
    'view_finance',
    'post_journal_entries',
    'run_payroll',
    'view_reports',
    'manage_notifications_templates',
    'manage_system_config',
    'manage_approval_thresholds',
    'manage_audit_settings',
]


# Per-role access matrix. Anything not listed is denied.
ROLE_PERMISSIONS = {
    'admin': {
        'sections': ALL_SECTIONS,
        'actions': ALL_ACTIONS,
    },
    'manager': {
        'sections': [
            'dashboard', 'pos', 'sales', 'shifts', 'products', 'discounts',
            'inventory', 'outlets', 'employees', 'fuel', 'accounting',
            'reports', 'notifications',
        ],
        'actions': [
            'open_shift', 'close_shift', 'process_sale', 'void_sale',
            'manage_products', 'adjust_stock', 'manage_discounts',
            'manage_outlets', 'manage_employees', 'manage_fuel_pumps',
            'manage_fuel_deliveries', 'confirm_reconciliation',
            'view_finance', 'view_reports',
            'manage_notifications_templates',
            'manage_system_config',
        ],
    },
    'accountant': {
        'sections': [
            'dashboard', 'sales', 'inventory', 'accounting', 'reports',
            'notifications',
        ],
        'actions': [
            'view_finance', 'post_journal_entries', 'run_payroll',
            'view_reports',
        ],
    },
    'cashier': {
        'sections': [
            'dashboard', 'pos', 'sales', 'shifts', 'products', 'fuel',
            'notifications',
        ],
        'actions': [
            'open_shift', 'close_shift', 'process_sale',
        ],
    },
    'attendant': {
        'sections': [
            'dashboard', 'pos', 'shifts', 'fuel', 'notifications',
        ],
        'actions': [
            'open_shift', 'close_shift', 'process_sale',
        ],
    },
}


def get_permissions_for_role(role):
    """Return the sections + actions allowed for a given role."""
    perms = ROLE_PERMISSIONS.get(role, {'sections': ['dashboard'], 'actions': []})
    return {
        'role': role,
        'sections': perms['sections'],
        'actions': perms['actions'],
    }
