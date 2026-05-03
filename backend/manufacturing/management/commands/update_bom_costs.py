from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, tenant_context
from manufacturing.models import BillOfMaterials
from decimal import Decimal


class Command(BaseCommand):
    help = 'Recalculates unit_cost on all active BOMs based on current product cost prices.'

    def handle(self, *args, **options):
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name='public')

        for tenant in tenants:
            with tenant_context(tenant):
                self.stdout.write(f"\n--- Tenant: {tenant.schema_name} ---")
                active_boms = BillOfMaterials.objects.filter(is_active=True)
                updated_count = 0
                unchanged_count = 0

                self.stdout.write(f"Updating costs for {active_boms.count()} active BOMs...")

                for bom in active_boms:
                    old_cost = bom.unit_cost
                    new_cost = bom.compute_unit_cost()

                    if old_cost != new_cost:
                        bom.unit_cost = new_cost
                        bom.save(update_fields=['unit_cost', 'updated_at'])
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated {bom.name}: {old_cost} → {new_cost}"
                            )
                        )
                    else:
                        unchanged_count += 1

                self.stdout.write(
                    f"Update complete. Updated {updated_count} BOMs. {unchanged_count} unchanged."
                )
