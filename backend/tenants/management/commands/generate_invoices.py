import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from tenants.models import TenantSubscription, SubscriptionInvoice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generates invoices for subscriptions entering a new billing cycle.'

    def handle(self, *args, **options):
        today = timezone.now()
        
        # 1. Find subscriptions where next_billing_date <= today
        due_subscriptions = TenantSubscription.objects.filter(
            next_billing_date__lte=today,
            status__in=[TenantSubscription.Status.ACTIVE, TenantSubscription.Status.TRIAL, TenantSubscription.Status.PAST_DUE]
        )
        
        count = 0
        for sub in due_subscriptions:
            try:
                with transaction.atomic():
                    # 2. Calculate next period
                    period_start = sub.next_billing_date
                    if sub.billing_cycle == TenantSubscription.BillingCycle.MONTHLY:
                        period_end = period_start + timedelta(days=30)
                        amount = sub.plan.price_monthly
                    else:
                        period_end = period_start + timedelta(days=365)
                        amount = sub.plan.price_annual
                    
                    # 3. Create invoice number
                    year = period_start.year
                    # Simple sequence for now; in prod use a more robust generator
                    last_invoice = SubscriptionInvoice.objects.filter(
                        invoice_number__startswith=f"INV-{year}"
                    ).order_by('-invoice_number').first()
                    
                    if last_invoice:
                        last_num = int(last_invoice.invoice_number.split('-')[-1])
                        new_num = last_num + 1
                    else:
                        new_num = 1
                    
                    invoice_number = f"INV-{year}-{new_num:05d}"
                    
                    # 4. Create SubscriptionInvoice
                    due_days = getattr(settings, 'INVOICE_DUE_DAYS', 14)
                    invoice = SubscriptionInvoice.objects.create(
                        subscription=sub,
                        invoice_number=invoice_number,
                        period_start=period_start.date(),
                        period_end=period_end.date(),
                        amount=amount,
                        status=SubscriptionInvoice.Status.PENDING,
                        due_date=period_start.date() + timedelta(days=due_days),
                        line_items=[{
                            "description": f"{sub.plan.name} Plan - {sub.get_billing_cycle_display()}",
                            "quantity": 1,
                            "unit_price": str(amount),
                            "total": str(amount)
                        }]
                    )
                    
                    # 5. Update subscription
                    sub.current_period_start = period_start
                    sub.current_period_end = period_end
                    sub.next_billing_date = period_end
                    
                    # If trial ended, move to ACTIVE (or PAST_DUE until invoice paid)
                    if sub.status == TenantSubscription.Status.TRIAL:
                        sub.status = TenantSubscription.Status.ACTIVE
                    
                    sub.save()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"Generated invoice {invoice_number} for {sub.tenant.name}"
                    ))
                    count += 1
            except Exception:
                logger.exception("Failed to generate invoice for subscription %s", sub.id)
                self.stderr.write(self.style.ERROR(
                    f"Failed to generate invoice for subscription {sub.id}"
                ))
                
        self.stdout.write(self.style.SUCCESS(f"Successfully generated {count} invoices."))
