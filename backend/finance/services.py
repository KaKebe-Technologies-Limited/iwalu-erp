from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Account, FiscalPeriod, JournalEntry, JournalEntryLine


def generate_entry_number():
    """Generate JE-YYYYMMDD-NNNN inside an atomic block."""
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"JE-{today}-"
    last = (
        JournalEntry.objects
        .select_for_update()
        .filter(entry_number__startswith=prefix)
        .order_by('-entry_number')
        .first()
    )
    if last:
        next_num = int(last.entry_number.split('-')[-1]) + 1
    else:
        next_num = 1
    return f"{prefix}{next_num:04d}"


def get_fiscal_period(date):
    """Find the fiscal period covering the given date, or auto-create a monthly one."""
    period = FiscalPeriod.objects.filter(
        start_date__lte=date, end_date__gte=date,
    ).first()
    if period:
        if period.is_closed:
            raise ValidationError(
                {'fiscal_period': f'Fiscal period "{period.name}" is closed.'}
            )
        return period
    # Auto-create monthly period
    import calendar
    first_day = date.replace(day=1)
    last_day = date.replace(day=calendar.monthrange(date.year, date.month)[1])
    return FiscalPeriod.objects.create(
        name=date.strftime('%B %Y'),
        start_date=first_day,
        end_date=last_day,
    )


def create_journal_entry(date, description, lines_data, source='manual',
                         reference_type='', reference_id=None,
                         created_by=None, auto_post=False):
    """
    Create a journal entry atomically.

    lines_data: list of dicts with keys:
        account_id, debit, credit, description (optional), outlet_id (optional)
    """
    with transaction.atomic():
        fiscal_period = get_fiscal_period(date)
        entry_number = generate_entry_number()

        total_debit = sum(Decimal(str(l.get('debit', 0))) for l in lines_data)
        total_credit = sum(Decimal(str(l.get('credit', 0))) for l in lines_data)
        if total_debit != total_credit:
            raise ValidationError({
                'lines': f'Debits ({total_debit}) must equal credits ({total_credit}).'
            })
        if total_debit == 0:
            raise ValidationError({'lines': 'Journal entry must have non-zero amounts.'})

        entry = JournalEntry.objects.create(
            entry_number=entry_number,
            date=date,
            fiscal_period=fiscal_period,
            description=description,
            source=source,
            reference_type=reference_type,
            reference_id=reference_id,
            status='draft',
            created_by=created_by or 0,
        )

        for line_data in lines_data:
            account = Account.objects.get(pk=line_data['account_id'])
            if not account.is_active:
                raise ValidationError({
                    'lines': f'Account "{account}" is inactive.'
                })
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=account,
                description=line_data.get('description', ''),
                debit=Decimal(str(line_data.get('debit', 0))),
                credit=Decimal(str(line_data.get('credit', 0))),
                outlet_id=line_data.get('outlet_id'),
            )

        if auto_post:
            post_journal_entry(entry, created_by)

    return entry


def post_journal_entry(entry, user_id):
    """Post a draft journal entry."""
    if entry.status != 'draft':
        raise ValidationError({'status': f'Cannot post a {entry.status} entry.'})

    total_debit = entry.lines.aggregate(s=Sum('debit'))['s'] or Decimal('0')
    total_credit = entry.lines.aggregate(s=Sum('credit'))['s'] or Decimal('0')
    if total_debit != total_credit:
        raise ValidationError({
            'lines': f'Debits ({total_debit}) must equal credits ({total_credit}).'
        })

    entry.status = 'posted'
    entry.posted_by = user_id
    entry.posted_at = timezone.now()
    entry.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_at'])
    return entry


def void_journal_entry(entry, user_id):
    """Void a posted entry by creating a reversal."""
    if entry.status != 'posted':
        raise ValidationError({'status': f'Cannot void a {entry.status} entry.'})

    reversal_lines = []
    for line in entry.lines.all():
        reversal_lines.append({
            'account_id': line.account_id,
            'debit': line.credit,
            'credit': line.debit,
            'description': f'Reversal: {line.description}',
            'outlet_id': line.outlet_id,
        })

    reversal = create_journal_entry(
        date=timezone.now().date(),
        description=f'Reversal of {entry.entry_number}: {entry.description}',
        lines_data=reversal_lines,
        source=entry.source,
        reference_type=entry.reference_type,
        reference_id=entry.reference_id,
        created_by=user_id,
        auto_post=True,
    )

    entry.status = 'voided'
    entry.voided_by = user_id
    entry.voided_at = timezone.now()
    entry.save(update_fields=['status', 'voided_by', 'voided_at', 'updated_at'])
    return reversal


# --- Automated journal entries ---

def _get_system_account(code):
    """Retrieve a system account by code or raise."""
    try:
        return Account.objects.get(code=code, is_system=True)
    except Account.DoesNotExist:
        raise ValidationError({
            'account': f'System account {code} not found. Run seed_chart_of_accounts.'
        })


def create_sale_journal_entry(sale):
    """Create journal entry when a sale is completed."""
    from sales.models import Payment

    lines = []
    payments = Payment.objects.filter(sale=sale)

    method_account_map = {
        'cash': '1000',
        'mobile_money': '1200',
        'bank_transfer': '1100',
        'card': '1100',
    }

    for payment in payments:
        account_code = method_account_map.get(payment.payment_method, '1000')
        lines.append({
            'account_id': _get_system_account(account_code).pk,
            'debit': payment.amount,
            'credit': Decimal('0'),
            'description': f'{payment.get_payment_method_display()} payment',
            'outlet_id': sale.outlet_id,
        })

    net_revenue = sale.subtotal - sale.discount_total
    if net_revenue > 0:
        lines.append({
            'account_id': _get_system_account('4000').pk,
            'debit': Decimal('0'),
            'credit': net_revenue,
            'description': 'Sales revenue',
            'outlet_id': sale.outlet_id,
        })

    if sale.tax_total > 0:
        lines.append({
            'account_id': _get_system_account('2100').pk,
            'debit': Decimal('0'),
            'credit': sale.tax_total,
            'description': 'VAT payable',
            'outlet_id': sale.outlet_id,
        })

    if not lines:
        return None

    return create_journal_entry(
        date=sale.created_at.date(),
        description=f'Sale {sale.receipt_number}',
        lines_data=lines,
        source='sale',
        reference_type='Sale',
        reference_id=sale.pk,
        created_by=sale.cashier_id,
        auto_post=True,
    )


def create_sale_void_journal_entry(sale, user_id):
    """Create reversal entry when a sale is voided."""
    je = JournalEntry.objects.filter(
        source='sale', reference_type='Sale', reference_id=sale.pk,
        status='posted',
    ).first()
    if je:
        return void_journal_entry(je, user_id)
    return None


def create_purchase_journal_entry(po, total_cost, user_id):
    """Create journal entry when a PO is received."""
    if total_cost <= 0:
        return None

    lines = [
        {
            'account_id': _get_system_account('1400').pk,
            'debit': total_cost,
            'credit': Decimal('0'),
            'description': 'Inventory received',
            'outlet_id': po.outlet_id,
        },
        {
            'account_id': _get_system_account('2000').pk,
            'debit': Decimal('0'),
            'credit': total_cost,
            'description': 'Accounts payable',
            'outlet_id': po.outlet_id,
        },
    ]

    return create_journal_entry(
        date=timezone.now().date(),
        description=f'Purchase order {po.po_number} received',
        lines_data=lines,
        source='purchase',
        reference_type='PurchaseOrder',
        reference_id=po.pk,
        created_by=user_id,
        auto_post=True,
    )


# --- Financial reports ---

def get_account_balance(account, as_of_date=None, outlet=None):
    """Calculate account balance from posted journal entries."""
    qs = JournalEntryLine.objects.filter(
        journal_entry__status='posted',
        account=account,
    )
    if as_of_date:
        qs = qs.filter(journal_entry__date__lte=as_of_date)
    if outlet:
        qs = qs.filter(outlet=outlet)

    totals = qs.aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    )
    total_debit = totals['total_debit'] or Decimal('0')
    total_credit = totals['total_credit'] or Decimal('0')

    # Assets and expenses have normal debit balance
    if account.account_type in ('asset', 'expense'):
        return total_debit - total_credit
    # Liabilities, equity, revenue have normal credit balance
    return total_credit - total_debit


def get_trial_balance(as_of_date=None, outlet=None):
    """Aggregate all account balances for trial balance."""
    accounts = Account.objects.filter(is_active=True)
    result = []
    for account in accounts:
        balance = get_account_balance(account, as_of_date, outlet)
        if balance != 0:
            result.append({
                'account_id': account.pk,
                'account_code': account.code,
                'account_name': account.name,
                'account_type': account.account_type,
                'debit': balance if balance > 0 and account.account_type in ('asset', 'expense') else (abs(balance) if balance < 0 and account.account_type in ('liability', 'equity', 'revenue') else Decimal('0')),
                'credit': balance if balance > 0 and account.account_type in ('liability', 'equity', 'revenue') else (abs(balance) if balance < 0 and account.account_type in ('asset', 'expense') else Decimal('0')),
                'balance': balance,
            })
    return result


def get_profit_and_loss(date_from, date_to, outlet=None):
    """Revenue and expense accounts for a period."""
    qs = JournalEntryLine.objects.filter(
        journal_entry__status='posted',
        journal_entry__date__gte=date_from,
        journal_entry__date__lte=date_to,
    )
    if outlet:
        qs = qs.filter(outlet=outlet)

    revenue_accounts = Account.objects.filter(
        account_type='revenue', is_active=True,
    )
    expense_accounts = Account.objects.filter(
        account_type='expense', is_active=True,
    )

    revenue_items = []
    total_revenue = Decimal('0')
    for account in revenue_accounts:
        lines = qs.filter(account=account)
        totals = lines.aggregate(d=Sum('debit'), c=Sum('credit'))
        balance = (totals['c'] or Decimal('0')) - (totals['d'] or Decimal('0'))
        if balance != 0:
            revenue_items.append({
                'account_code': account.code,
                'account_name': account.name,
                'amount': balance,
            })
            total_revenue += balance

    expense_items = []
    total_expenses = Decimal('0')
    for account in expense_accounts:
        lines = qs.filter(account=account)
        totals = lines.aggregate(d=Sum('debit'), c=Sum('credit'))
        balance = (totals['d'] or Decimal('0')) - (totals['c'] or Decimal('0'))
        if balance != 0:
            expense_items.append({
                'account_code': account.code,
                'account_name': account.name,
                'amount': balance,
            })
            total_expenses += balance

    return {
        'date_from': date_from,
        'date_to': date_to,
        'revenue': revenue_items,
        'total_revenue': total_revenue,
        'expenses': expense_items,
        'total_expenses': total_expenses,
        'net_income': total_revenue - total_expenses,
    }


def get_balance_sheet(as_of_date=None, outlet=None):
    """Assets, liabilities, and equity as of date."""
    type_groups = {
        'asset': [],
        'liability': [],
        'equity': [],
    }
    totals = {k: Decimal('0') for k in type_groups}

    for account in Account.objects.filter(
        account_type__in=type_groups.keys(), is_active=True,
    ):
        balance = get_account_balance(account, as_of_date, outlet)
        if balance != 0:
            type_groups[account.account_type].append({
                'account_code': account.code,
                'account_name': account.name,
                'balance': balance,
            })
            totals[account.account_type] += balance

    # Add retained earnings (net income to date) into equity
    pnl = get_profit_and_loss(
        date_from='1900-01-01',
        date_to=as_of_date or timezone.now().date(),
        outlet=outlet,
    )
    retained = pnl['net_income']
    if retained != 0:
        type_groups['equity'].append({
            'account_code': 'RE',
            'account_name': 'Retained Earnings (computed)',
            'balance': retained,
        })
        totals['equity'] += retained

    return {
        'as_of_date': as_of_date or timezone.now().date(),
        'assets': type_groups['asset'],
        'total_assets': totals['asset'],
        'liabilities': type_groups['liability'],
        'total_liabilities': totals['liability'],
        'equity': type_groups['equity'],
        'total_equity': totals['equity'],
        'total_liabilities_and_equity': totals['liability'] + totals['equity'],
    }


def get_account_ledger(account_id, date_from=None, date_to=None):
    """All posted journal lines for an account, with running balance."""
    account = Account.objects.get(pk=account_id)
    qs = JournalEntryLine.objects.filter(
        journal_entry__status='posted',
        account=account,
    ).select_related('journal_entry').order_by('journal_entry__date', 'id')

    if date_from:
        qs = qs.filter(journal_entry__date__gte=date_from)
    if date_to:
        qs = qs.filter(journal_entry__date__lte=date_to)

    running_balance = Decimal('0')
    entries = []
    for line in qs:
        if account.account_type in ('asset', 'expense'):
            running_balance += line.debit - line.credit
        else:
            running_balance += line.credit - line.debit
        entries.append({
            'date': line.journal_entry.date,
            'entry_number': line.journal_entry.entry_number,
            'description': line.description or line.journal_entry.description,
            'debit': line.debit,
            'credit': line.credit,
            'balance': running_balance,
        })

    return {
        'account_code': account.code,
        'account_name': account.name,
        'account_type': account.account_type,
        'entries': entries,
    }
