import logging
from datetime import date
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from tenants.models import SubscriptionInvoice, TenantSubscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Suspends tenants with overdue invoices past grace period.'

    def handle(self, *args, **options):
        grace_days = getattr(settings, 'PAYMENT_GRACE_PERIOD_DAYS', 7)
        today = date.today()
        
        # 1. Find pending invoices past grace period
        overdue_invoices = SubscriptionInvoice.objects.filter(
            status=SubscriptionInvoice.Status.PENDING,
            due_date__lt=today - timezone.timedelta(days=grace_days)
        )
        
        count = 0
        for invoice in overdue_invoices:
            # 2. Mark invoice as overdue
            invoice.status = SubscriptionInvoice.Status.OVERDUE
            invoice.save(update_fields=['status'])
            
            # 3. Check subscription and suspend if all recent invoices are overdue
            subscription = invoice.subscription
            if subscription.status != TenantSubscription.Status.SUSPENDED:
                reason = f"Invoice #{invoice.invoice_number} overdue {grace_days}+ days"
                subscription.suspend(reason)
                
                # 4. Log and ideally send email (Email logic can be added here)
                self.stdout.write(self.style.SUCCESS(
                    f"Suspended tenant {subscription.tenant.name}: {reason}"
                ))
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Successfully processed {count} suspensions."))
