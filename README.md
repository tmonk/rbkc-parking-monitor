# RBKC Parking Suspension Monitor

Home Assistant automation that reads RBKC suspension alert emails, geocodes your car location, and warns if you are in or near a suspended bay.

## What you get (from `packages/parking_monitor.yaml`)

- Helpers: `input_text.car_current_street` (persisted; seeded to RBKC Town Hall on first start), `input_boolean.parking_debug_mode`
- Binary sensor: `binary_sensor.car_in_suspended_bay` with active/upcoming attributes and status text
- Automation: listens for `imap_content` events, daily at 08:00, startup, or when the car location changes; calls `pyscript.check_parking`; sends notifications via `notify.notify`
- Dashboard: YAML Lovelace view at `dashboards/parking_dashboard.yaml` automatically exposed as “Parking Monitor”
- Device trackers: `device_tracker.parking_monitor_car` plus up to 5 `sus_active_*` entities for mapping

## Requirements

- Home Assistant 2025.x
- PyScript (HACS)
- IMAP integration pointed at your inbox
- RBKC suspension email subscription

## Install & Set Up

1. Subscribe to RBKC suspension emails.
2. Install PyScript via HACS → Integrations → install → restart.
3. Add this repo in HACS (⋮ → Custom repositories) → category: Python Script → download.
4. Ensure `configuration.yaml` has:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
5. Add IMAP integration with Search exactly: `SUBJECT "Parking Suspensions Email Alert"`.
6. Restart Home Assistant so the package loads (helpers, automation, dashboard registration).
7. Open the “Parking Monitor” dashboard in the sidebar (provided by the package). If it does not appear, verify `dashboards/parking_dashboard.yaml` exists.
8. Set your street in the dashboard helper. Update the notify target in the package automation if `notify.notify` is not valid in your setup.

## Configure & Tune

- **Car location**: set via dashboard helper (persists). Fallback default lives in `/config/pyscript/persist_car_location.py`.
- **Default backup location**: `Town Hall, Hornton Street` is stored in `pyscript.car_location_backup` until you set your own.
- **Proximity**: `/config/pyscript/check_parking.py` compare distance (default `<= 100` meters). Adjust for tighter/looser matches.
- **Upcoming window**: same file, change `datetime.timedelta(days=7)`.
- **Geocode region hint**: `/config/pyscript_modules/parking_utils.py` query string defaults to Kensington and Chelsea; edit for your area.
- **Dashboard tweaks**: headers/colors near the top of `dashboards/parking_dashboard.yaml`; map zoom via `default_zoom: 16`.
- **Caches**: email cache `/config/parking_email_cache.txt`, geocode cache `/config/parking_geo_cache.json`. Delete and restart to refresh.

## Quick checks

- `binary_sensor.car_in_suspended_bay` exists after restart.
- Cache files appear after first run.
- If parsing seems off, confirm the IMAP Search string matches the exact RBKC subject and include a house number in your stored street.

## Expected Email Format

Expected email block:
```
APPROVED SUSPENSION
Street Name: Example Street
Location: Outside No. 12-18
From Date: 25/11/2024
To Date: 29/11/2024
```
It extracts the street, location text, and start/end dates, then matches suspensions within ~100m of your stored car location.

## Files

- `pyscript/check_parking.py` - parse email, geocode, set entities
- `pyscript/persist_car_location.py` - remember car location
- `pyscript_modules/parking_utils.py` - caching/geocode helpers
- `packages/parking_monitor.yaml` - helpers, dashboard, entities
- `dashboards/parking_dashboard.yaml` - Lovelace view

## Data & Privacy

- Email bodies cached locally at `/config/parking_email_cache.txt`
- Geocoding via OpenStreetMap Nominatim; results cached at `/config/parking_geo_cache.json`
- No data leaves your Home Assistant beyond those geocoding requests