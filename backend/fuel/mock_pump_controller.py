#!/usr/bin/env python3
"""
Mock Pump Controller — Nexus ERP Development Tool

Simulates a fuel pump hardware controller for development and testing.
Sends realistic pump events to the local API so you can test the full
fuel-sale workflow without physical hardware.

Usage:
    python backend/fuel/mock_pump_controller.py [options]

Examples:
    # Simulate 4 pumps at outlet 1, customer every 30 seconds
    python backend/fuel/mock_pump_controller.py --pumps 4 --outlet 1 --interval 30

    # Dry run — print events without sending to API
    python backend/fuel/mock_pump_controller.py --pumps 2 --dry-run

    # Point at staging server with a specific API key
    python backend/fuel/mock_pump_controller.py \\
        --api-url https://staging.nexuserp.com/api \\
        --api-key my-prod-key \\
        --pumps 6 --interval 60

    # Fast mode for testing — very short dispense intervals
    python backend/fuel/mock_pump_controller.py --interval 3 --dispense-speed 200
"""

import argparse
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('mock-pump')

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_API_URL = 'http://localhost:8000/api'
DEFAULT_API_KEY = 'dev-pump-key-change-in-production'
DEFAULT_PUMP_COUNT = 2
DEFAULT_INTERVAL = 30       # seconds between customers per pump
DEFAULT_DISPENSE_SPEED = 40  # litres per minute

# Realistic fuel prices in UGX (as of 2026, Uganda)
FUEL_PRICES_UGX = {
    'petrol': Decimal('5500'),
    'diesel': Decimal('5200'),
    'kerosene': Decimal('4800'),
}
DEFAULT_FUEL_TYPE = 'petrol'


# ---------------------------------------------------------------------------
# Pump simulator state
# ---------------------------------------------------------------------------
class PumpSimulator:
    """Tracks the state of a single simulated pump."""

    def __init__(self, pump_id: int, pump_number: int, fuel_type: str = DEFAULT_FUEL_TYPE):
        self.pump_id = pump_id
        self.pump_number = pump_number
        self.fuel_type = fuel_type
        self.fuel_price = FUEL_PRICES_UGX.get(fuel_type, FUEL_PRICES_UGX['petrol'])
        # Start meter at a realistic cumulative reading (litres since installation)
        self.meter = Decimal(str(random.uniform(50000, 200000))).quantize(Decimal('0.001'))
        self.busy = False
        log.info(
            f'  Pump {pump_number} (id={pump_id}) | {fuel_type} @ '
            f'{self.fuel_price:,} UGX/L | meter={self.meter}L'
        )

    def simulate_customer(self) -> list[dict]:
        """
        Simulate one customer dispensing fuel.
        Returns a list of events: authorised → (1-3 flowing) → completed.
        """
        self.busy = True

        # Decide how much to dispense: random 5–200 litres
        litres = Decimal(str(random.uniform(5, 200))).quantize(Decimal('0.001'))
        amount = (litres * self.fuel_price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        meter_start = self.meter
        meter_end = (self.meter + litres).quantize(Decimal('0.001'))

        events = []
        now = datetime.now(tz=timezone.utc)

        # Event 1: authorised
        events.append(self._build_event('authorised', meter_start=meter_start, now=now))

        # Event 2+: flowing (1–3 intermediate readings as fuel flows)
        flowing_count = random.randint(1, 3)
        for i in range(flowing_count):
            partial_end = meter_start + (litres * Decimal(str((i + 1) / (flowing_count + 1))))
            partial_end = partial_end.quantize(Decimal('0.001'))
            events.append(self._build_event('flowing', meter_end=partial_end, now=now))

        # Final event: completed
        events.append(self._build_event(
            'completed',
            litres=litres,
            amount_ugx=amount,
            meter_start=meter_start,
            meter_end=meter_end,
            now=now,
        ))

        self.meter = meter_end
        self.busy = False
        return events

    def _build_event(
        self, event_type: str, *,
        litres=None, amount_ugx=None,
        meter_start=None, meter_end=None,
        now=None,
    ) -> dict:
        payload = {
            'pump_id': self.pump_id,
            'event_type': event_type,
            'source': 'mock',
            'occurred_at': (now or datetime.now(tz=timezone.utc)).isoformat(),
        }
        if meter_start is not None:
            payload['meter_start'] = str(meter_start)
        if meter_end is not None:
            payload['meter_end'] = str(meter_end)
        if litres is not None:
            payload['litres'] = str(litres)
        if amount_ugx is not None:
            payload['amount_ugx'] = str(amount_ugx)
        return payload


# ---------------------------------------------------------------------------
# API sender
# ---------------------------------------------------------------------------
def send_event(event: dict, api_url: str, api_key: str, dry_run: bool) -> bool:
    """POST a single pump event to the API. Returns True on success."""
    if dry_run:
        log.info(f'[DRY-RUN] {json.dumps(event, indent=2)}')
        return True

    url = f'{api_url.rstrip("/")}/fuel/pump-events/'
    body = json.dumps(event).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-Pump-API-Key': api_key,
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 201:
                data = json.loads(resp.read())
                log.info(
                    f'  → Sent: pump={event["pump_id"]} type={event["event_type"]} '
                    f'[event_id={data.get("id")}]'
                )
                return True
            else:
                log.warning(f'  → Unexpected status {resp.status} for {event["event_type"]}')
                return False
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        log.error(f'  → HTTP {e.code}: {body[:200]}')
        return False
    except urllib.error.URLError as e:
        log.error(f'  → Connection error: {e.reason}')
        return False
    except Exception as e:
        log.error(f'  → Unexpected error: {e}')
        return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run(args):
    log.info('=== Nexus ERP Mock Pump Controller ===')
    log.info(f'API:      {args.api_url}')
    log.info(f'Pumps:    {args.pumps}')
    log.info(f'Outlet:   {args.outlet}')
    log.info(f'Interval: {args.interval}s between customers per pump')
    log.info(f'Dry-run:  {args.dry_run}')
    log.info('')

    # Initialise pump simulators
    # pump_id is assumed to be sequential starting from args.pump_id_start
    pumps = [
        PumpSimulator(
            pump_id=args.pump_id_start + i,
            pump_number=i + 1,
            fuel_type=args.fuel_type,
        )
        for i in range(args.pumps)
    ]
    log.info(f'Initialised {len(pumps)} pump(s). Starting simulation...')
    log.info('')

    stats = {'sent': 0, 'failed': 0, 'customers': 0}

    try:
        while True:
            # Pick a random available pump
            available = [p for p in pumps if not p.busy]
            if not available:
                time.sleep(1)
                continue

            pump = random.choice(available)
            stats['customers'] += 1
            log.info(
                f'Customer #{stats["customers"]} at Pump {pump.pump_number} '
                f'(id={pump.pump_id})'
            )

            events = pump.simulate_customer()

            for event in events:
                success = send_event(event, args.api_url, args.api_key, args.dry_run)
                if success:
                    stats['sent'] += 1
                else:
                    stats['failed'] += 1
                # Small delay between events in a sequence (realistic)
                time.sleep(0.5)

            log.info(
                f'  Dispensed {events[-1].get("litres")}L | '
                f'{events[-1].get("amount_ugx")} UGX | '
                f'meter now {pump.meter}L'
            )
            log.info(
                f'  Stats: sent={stats["sent"]} failed={stats["failed"]} '
                f'customers={stats["customers"]}'
            )

            # Wait before next customer
            jitter = random.uniform(0.5, 1.5)
            sleep_time = args.interval * jitter
            log.info(f'  Next customer in {sleep_time:.1f}s...')
            log.info('')
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info('')
        log.info('Simulation stopped.')
        log.info(
            f'Final stats: {stats["customers"]} customers, '
            f'{stats["sent"]} events sent, {stats["failed"]} failed.'
        )


def main():
    parser = argparse.ArgumentParser(
        description='Nexus ERP Mock Pump Controller — simulates fuel pump hardware events.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--api-url', default=DEFAULT_API_URL,
        help=f'Base API URL (default: {DEFAULT_API_URL})',
    )
    parser.add_argument(
        '--api-key', default=DEFAULT_API_KEY,
        help='X-Pump-API-Key value (default: dev key)',
    )
    parser.add_argument(
        '--pumps', type=int, default=DEFAULT_PUMP_COUNT,
        help=f'Number of pumps to simulate (default: {DEFAULT_PUMP_COUNT})',
    )
    parser.add_argument(
        '--outlet', type=int, default=1,
        help='Outlet ID (informational only, default: 1)',
    )
    parser.add_argument(
        '--pump-id-start', type=int, default=1,
        help='First pump_id in the database (default: 1)',
    )
    parser.add_argument(
        '--interval', type=float, default=DEFAULT_INTERVAL,
        help=f'Seconds between customers (default: {DEFAULT_INTERVAL})',
    )
    parser.add_argument(
        '--dispense-speed', type=float, default=DEFAULT_DISPENSE_SPEED,
        help=f'Litres per minute (default: {DEFAULT_DISPENSE_SPEED}, informational)',
    )
    parser.add_argument(
        '--fuel-type', default=DEFAULT_FUEL_TYPE,
        choices=['petrol', 'diesel', 'kerosene'],
        help=f'Fuel type to simulate (default: {DEFAULT_FUEL_TYPE})',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print events without sending to API',
    )

    args = parser.parse_args()

    if args.pumps < 1 or args.pumps > 20:
        parser.error('--pumps must be between 1 and 20')
    if args.interval < 1:
        parser.error('--interval must be at least 1 second')

    run(args)


if __name__ == '__main__':
    main()
