from django.core.management.base import BaseCommand
from finance.models import Account


DEFAULT_ACCOUNTS = [
    # Assets (1xxx)
    ('1000', 'Cash', 'asset'),
    ('1100', 'Bank Account', 'asset'),
    ('1200', 'Mobile Money Account', 'asset'),
    ('1300', 'Accounts Receivable', 'asset'),
    ('1400', 'Inventory', 'asset'),
    # Liabilities (2xxx)
    ('2000', 'Accounts Payable', 'liability'),
    ('2100', 'VAT Payable', 'liability'),
    ('2200', 'NSSF Payable', 'liability'),
    ('2300', 'PAYE Payable', 'liability'),
    ('2400', 'Net Salary Payable', 'liability'),
    # Equity (3xxx)
    ('3000', "Owner's Equity", 'equity'),
    ('3100', 'Retained Earnings', 'equity'),
    # Revenue (4xxx)
    ('4000', 'Sales Revenue', 'revenue'),
    ('4100', 'Discount Given', 'revenue'),
    # Expenses (5xxx)
    ('5000', 'Cost of Goods Sold', 'expense'),
    ('5100', 'Salary Expense', 'expense'),
    ('5200', 'NSSF Employer Contribution', 'expense'),
    ('5300', 'Rent Expense', 'expense'),
    ('5400', 'Utilities Expense', 'expense'),
    ('5500', 'General Expense', 'expense'),
]


class Command(BaseCommand):
    help = 'Seed the default chart of accounts for the current tenant'

    def handle(self, *args, **options):
        created_count = 0
        for code, name, account_type in DEFAULT_ACCOUNTS:
            _, created = Account.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account_type': account_type,
                    'is_system': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created: {code} - {name}')
            else:
                self.stdout.write(f'  Exists:  {code} - {name}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created {created_count} accounts, '
            f'{len(DEFAULT_ACCOUNTS) - created_count} already existed.'
        ))
