"""
Retry failed EFRIS fiscal invoice submissions.

Usage:
    python manage.py retry_efris [--limit 100]

Designed to be run periodically via cron (e.g. every 5 minutes). Walks all
tenant schemas and retries any FiscalInvoice in 'failed' status up to
MAX_RETRY_ATTEMPTS.
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, tenant_context

from fiscalization import services


class Command(BaseCommand):
    help = 'Retry failed EFRIS fiscal invoice submissions across all tenants.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Maximum number of invoices to retry per tenant (default: 100)',
        )
        parser.add_argument(
            '--tenant', type=str, default=None,
            help='Only retry for this specific tenant schema',
        )

    def handle(self, *args, **options):
        Tenant = get_tenant_model()
        limit = options['limit']
        target_schema = options['tenant']

        tenants = Tenant.objects.exclude(schema_name='public')
        if target_schema:
            tenants = tenants.filter(schema_name=target_schema)

        grand_total = {'retried': 0, 'succeeded': 0, 'still_failing': 0, 'exhausted': 0}

        for tenant in tenants:
            with tenant_context(tenant):
                stats = services.retry_failed_invoices(limit=limit)
                self.stdout.write(
                    f'[{tenant.schema_name}] retried={stats["retried"]} '
                    f'succeeded={stats["succeeded"]} '
                    f'still_failing={stats["still_failing"]} '
                    f'exhausted={stats["exhausted"]}'
                )
                for k in grand_total:
                    grand_total[k] += stats[k]

        self.stdout.write(self.style.SUCCESS(
            f'Done. total: {grand_total}'
        ))
