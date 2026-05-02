from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from cafe.models import WasteLog
from notifications.services import create_notification
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Identify products near expiry based on WasteLog trends and notify managers'

    def handle(self, *args, **options):
        User = get_user_model()
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        # Products with 3+ expired logs in the last 7 days
        expired_trends = WasteLog.objects.filter(
            reason=WasteLog.Reason.EXPIRED,
            recorded_at__gte=seven_days_ago
        ).values('product', 'product__name').annotate(
            expired_count=Count('id')
        ).filter(expired_count__gte=3)

        if not expired_trends.exists():
            self.stdout.write(self.style.SUCCESS('No recurring expiry trends found.'))
            return

        # Notify managers
        managers = User.objects.filter(role__in=['admin', 'manager'])
        
        for trend in expired_trends:
            product_name = trend['product__name']
            count = trend['expired_count']
            message = f"Product '{product_name}' has been logged as expired {count} times in the last 7 days. Please review stock levels and ordering."
            
            for manager in managers:
                create_notification(
                    recipient_id=manager.id,
                    notification_type='expiry_alert',
                    title=f"Recurring Expiry: {product_name}",
                    body=message,
                    priority='high',
                    source_type='Product',
                    reference_id=trend['product']
                )
            
            self.stdout.write(self.style.WARNING(f"Trend found: {product_name} ({count} expirations)"))

        self.stdout.write(self.style.SUCCESS(f"Finished checking expiry trends. {expired_trends.count()} alerts generated."))
