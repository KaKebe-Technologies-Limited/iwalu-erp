import re
from django.core.management.base import BaseCommand, CommandError
from tenants.models import Client, Domain


class Command(BaseCommand):
    help = 'Create a new tenant with a domain'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Business name')
        parser.add_argument('domain', type=str, help='Domain (e.g. demo.localhost)')
        parser.add_argument(
            '--schema', type=str, default=None,
            help='Schema name (auto-generated from name if not provided)',
        )

    def handle(self, *args, **options):
        name = options['name']
        domain = options['domain']
        schema_name = options['schema'] or self._slugify(name)

        if Client.objects.filter(schema_name=schema_name).exists():
            raise CommandError(f'Tenant with schema "{schema_name}" already exists.')

        if Domain.objects.filter(domain=domain).exists():
            raise CommandError(f'Domain "{domain}" is already in use.')

        self.stdout.write(f'Creating tenant "{name}" (schema: {schema_name})...')
        tenant = Client(schema_name=schema_name, name=name)
        tenant.save()

        Domain.objects.create(domain=domain, tenant=tenant, is_primary=True)

        self.stdout.write(self.style.SUCCESS(
            f'Tenant "{name}" created successfully.\n'
            f'  Schema: {schema_name}\n'
            f'  Domain: {domain}'
        ))

    def _slugify(self, name):
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug
