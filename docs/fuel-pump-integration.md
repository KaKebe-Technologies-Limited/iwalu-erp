# Fuel Pump Hardware Integration Guide

**Status**: API contract implemented. Mock controller available. Real hardware adapter deferred pending client hardware confirmation.

---

## 1. Overview

Nexus ERP integrates with fuel pump controllers via a webhook-style HTTP endpoint. The pump controller (hardware or mock) sends events to the ERP API as fuel is dispensed. The ERP records these events, auto-updates pump readings, and feeds data into shift reconciliation and fuel stock tracking.

```
Pump hardware / mock controller
        │
        │  POST /api/fuel/pump-events/
        │  Header: X-Pump-API-Key: <key>
        ▼
Nexus ERP API  →  PumpEvent record  →  PumpReading auto-close  →  Shift reconciliation
```

---

## 2. API Contract

### Endpoint

```
POST /api/fuel/pump-events/
GET  /api/fuel/pump-events/?pump_id=X&limit=50
```

### Authentication

Hardware controllers authenticate with an API key (not JWT):

```
Header: X-Pump-API-Key: <PUMP_CONTROLLER_API_KEY>
```

Set `PUMP_CONTROLLER_API_KEY` in `.env`. The development default is `dev-pump-key-change-in-production`.

### Event Types

| `event_type`  | When to send | Required fields |
|---|---|---|
| `authorised`  | Pump nozzle lifted, dispense authorised | `pump_id`, `occurred_at`, `meter_start` |
| `flowing`     | Fuel actively flowing (send every ~5 seconds) | `pump_id`, `occurred_at`, `meter_end` |
| `completed`   | Nozzle replaced, dispense finished | `pump_id`, `occurred_at`, `litres`, `amount_ugx`, `meter_start`, `meter_end` |
| `error`       | Hardware fault or transaction cancelled | `pump_id`, `occurred_at` |

### Request Body

```json
{
  "pump_id": 1,
  "event_type": "completed",
  "litres": "45.250",
  "amount_ugx": "249000",
  "meter_start": "10000.000",
  "meter_end": "10045.250",
  "attendant_id": null,
  "source": "hardware",
  "occurred_at": "2026-05-13T10:00:00Z"
}
```

All decimal fields are strings to avoid floating-point precision loss.
`amount_ugx` is a whole number (UGX has no fractional subdivision).

### Response (201 Created)

```json
{
  "id": 42,
  "pump": 1,
  "pump_number": 1,
  "event_type": "completed",
  "event_type_display": "Completed",
  "litres": "45.250",
  "amount_ugx": "249000",
  "meter_start": "10000.000",
  "meter_end": "10045.250",
  "attendant_id": null,
  "source": "hardware",
  "source_display": "Hardware Controller",
  "raw_payload": { "...": "original request body" },
  "occurred_at": "2026-05-13T10:00:00Z",
  "created_at": "2026-05-13T10:00:01Z"
}
```

### Auto-close behaviour

When a `completed` event is received with `meter_end` set, the API automatically finds the most recent open `PumpReading` for that pump (where `closing_reading` is null) and sets `closing_reading = meter_end`. This links hardware events to the shift-based reconciliation workflow without requiring the hardware to know about shifts.

---

## 3. Mock Pump Controller

A development tool that simulates pump hardware events. Use this during development and testing instead of real hardware.

### Location

```
backend/fuel/mock_pump_controller.py
```

### Requirements

Python 3.10+ with no external dependencies (uses only stdlib).

### Usage

```bash
# Basic: 2 pumps, customer every 30 seconds
python backend/fuel/mock_pump_controller.py

# 4 pumps, customer every 10 seconds (fast testing)
python backend/fuel/mock_pump_controller.py --pumps 4 --interval 10

# Dry run: print events without sending
python backend/fuel/mock_pump_controller.py --dry-run

# Diesel pumps at outlet 2, custom pump IDs
python backend/fuel/mock_pump_controller.py \
    --pumps 3 --outlet 2 --pump-id-start 5 \
    --fuel-type diesel --interval 20

# Point at staging
python backend/fuel/mock_pump_controller.py \
    --api-url https://staging.nexuserp.com/api \
    --api-key prod-pump-key-here \
    --pumps 6
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--api-url` | `http://localhost:8000/api` | API base URL |
| `--api-key` | dev default | X-Pump-API-Key value |
| `--pumps` | `2` | Number of pumps to simulate |
| `--outlet` | `1` | Outlet ID (informational) |
| `--pump-id-start` | `1` | First pump_id in the database |
| `--interval` | `30` | Seconds between customers |
| `--fuel-type` | `petrol` | One of: petrol, diesel, kerosene |
| `--dry-run` | false | Print events, don't send |

### What it simulates

1. Customer arrives at a random available pump
2. `authorised` event sent
3. 1–3 `flowing` events sent (partial meter readings)
4. `completed` event sent (total litres: 5–200L, realistic UGX amount)
5. Waits `interval × random(0.5–1.5)` seconds before next customer

---

## 4. Real Hardware Integration (Deferred)

The real hardware adapter will be a separate Python service (not part of Django) that:
1. Connects to the pump site controller via the appropriate protocol
2. Translates hardware events into the Nexus API format
3. POSTs to `/api/fuel/pump-events/`

The adapter is a thin translation layer — all business logic stays in the API.

### Supported protocol targets (once hardware is confirmed)

| Protocol | Common hardware | Adapter complexity |
|---|---|---|
| **IFSF** (TCP/IP) | Gilbarco, Wayne/MECO, Tatsuno | Medium — well-documented standard |
| **Gilbarco CRL** (serial) | Gilbarco Advantage, Encore | High — proprietary |
| **Wayne DART** (serial) | Wayne Helix, Reliant | High — proprietary |
| **Pulse output** | Generic Chinese pumps, older units | Low — count pulses via GPIO |
| **Tokheim Quantium** | Tokheim Q series | Medium |
| **FuelNet / Insite360** | Any (via site management software) | Low — they provide an API |

---

## 5. Client Hardware Questionnaire

**Ask the client these questions before building the real adapter.** Record answers in this section.

### 5.1 Pump Hardware

- [ ] **Pump brand**: Gilbarco / Wayne / Tokheim / Tatsuno / Piusi / generic Chinese / other: ___
- [ ] **Pump model**: e.g., Gilbarco Encore 500S, Wayne Helix 6000, etc.
- [ ] **Number of pumps**: ___
- [ ] **Hoses per pump**: 1 hose / 2 hoses (bi-fuel)
- [ ] **Are these new pumps being purchased, or existing pumps already installed?**
- [ ] **Pump age** (approximate year of installation): ___

### 5.2 Site Controller

A site controller is a box (often in the pump room) that aggregates data from all pumps.

- [ ] **Is there a site controller?** Yes / No
- [ ] **Site controller brand/model**: e.g., Gilbarco Commander, Wayne DOMS, Hectronic, etc.
- [ ] **Does the site controller have a network (Ethernet) port?** Yes / No
- [ ] **Does the site controller have a serial (RS-232 or RS-485) port?** Yes / No

### 5.3 Communication

- [ ] **How does the pump controller communicate?**
  - [ ] TCP/IP over Ethernet (LAN)
  - [ ] RS-232 serial cable
  - [ ] RS-485 serial (multi-drop)
  - [ ] USB
  - [ ] Pulse output (wire per litre)
  - [ ] Wireless (Wi-Fi / GSM)
  - [ ] Unknown / need to check with supplier

- [ ] **Is there existing pump management software?** (e.g., Gilbarco Passport, Insite360, FuelNet, T-Rex, other)
  - If yes: does that software have an API or data export? Yes / No / Unknown

### 5.4 Network Setup at Station

- [ ] **Is there a local area network (LAN) at the fuel station?** Yes / No
- [ ] **Internet connectivity type**: Fibre / 4G LTE / 3G / None
- [ ] **Is the Nexus ERP server local (on-site) or cloud-hosted?** Cloud / On-site / Both

### 5.5 Receipt Printing at Pump

- [ ] **Do the pumps print their own receipts?** Yes / No
- [ ] **If yes**: should Nexus ERP receipts replace or supplement pump receipts?
- [ ] **Is EFRIS fiscalisation required on fuel receipts?** Yes (mandatory by URA) / No / Unsure

### 5.6 Answers (fill in when client responds)

```
Pump brand/model:
Number of pumps:
Hoses per pump:
Site controller:
Protocol:
Network:
Existing software:
Notes:
```

---

## 6. Environment Variables

Add to `.env` and `.env.example`:

```env
# Fuel pump controller API key
# Hardware controllers send this in the X-Pump-API-Key header.
# Generate a strong random string for production.
PUMP_CONTROLLER_API_KEY=dev-pump-key-change-in-production
```

---

## 7. Testing the Endpoint

```bash
# Start Docker stack
docker compose up -d

# Send a completed pump event (development key)
curl -X POST http://localhost:8000/api/fuel/pump-events/ \
  -H "Content-Type: application/json" \
  -H "X-Pump-API-Key: dev-pump-key-change-in-production" \
  -d '{
    "pump_id": 1,
    "event_type": "completed",
    "litres": "45.250",
    "amount_ugx": "249000",
    "meter_start": "10000.000",
    "meter_end": "10045.250",
    "source": "mock",
    "occurred_at": "2026-05-13T10:00:00Z"
  }'

# List recent events
curl http://localhost:8000/api/fuel/pump-events/?limit=10 \
  -H "X-Pump-API-Key: dev-pump-key-change-in-production"

# Run the mock controller (fast mode for testing)
python backend/fuel/mock_pump_controller.py --pumps 2 --interval 5 --dry-run
```

---

*Last updated: May 2026*
