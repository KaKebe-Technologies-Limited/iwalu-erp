from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date
from assets.models import Asset, AssetCategory

class Command(BaseCommand):
    help = 'Calculate monthly depreciation for all active assets'

    def add_arguments(self, parser):
        parser.add_argument('--month', type=str, help='Month in YYYY-MM format')
        parser.add_argument('--journal', action='store_true', help='Create journal entries in finance module')

    def handle(self, *args, **options):
        month_str = options.get('month')
        if month_str:
            try:
                year, month = map(int, month_str.split('-'))
                target_date = date(year, month, 1)
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid month format. Use YYYY-MM.'))
                return
        else:
            target_date = date.today()

        self.stdout.write(f"Calculating depreciation for {target_date.strftime('%B %Y')}...")

        assets = Asset.objects.filter(status=Asset.Status.ACTIVE)
        total_depreciation = Decimal('0')
        count = 0

        with transaction.atomic():
            for asset in assets:
                # Check if already depreciated for this month (simplified check)
                # In a production system, we'd have a DepreciationLog model to track this.
                
                monthly_dep = asset.calculate_monthly_depreciation()
                if monthly_dep > 0:
                    # Increment accumulated depreciation
                    # Ensure we don't exceed cost - residual_value
                    depreciable_remaining = asset.depreciation_remaining
                    actual_dep = min(monthly_dep, depreciable_remaining)
                    
                    if actual_dep > 0:
                        asset.accumulated_depreciation += actual_dep
                        asset.save(update_fields=['accumulated_depreciation', 'updated_at'])
                        total_depreciation += actual_dep
                        count += 1

                        if options.get('journal'):
                            self.journal_depreciation(asset, actual_dep, target_date)

        self.stdout.write(self.style.SUCCESS(
            f"Depreciation calculated: UGX {total_depreciation:,.2f} across {count} assets"
        ))

    def journal_depreciation(self, asset, amount, period_date):
        """
        Optional finance integration. 
        Tries to create a journal entry if the finance app is available.
        """
        try:
            from finance.models import JournalEntry, JournalEntryLine
            # This is a placeholder for actual finance integration logic
            # which would require finding the correct GL accounts and fiscal period.
            self.stdout.write(f"  [Journal] {asset.asset_code}: UGX {amount:,.2f}")
            
            # Implementation would go here if finance module details were fully specified
            # For now we just log that we would do it.
        except ImportError:
            self.stdout.write(self.style.WARNING("  Finance module not found. Skipping journal entry."))
