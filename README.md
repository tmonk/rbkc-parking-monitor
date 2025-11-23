# RBKC Parking Suspension Monitor

Home Assistant custom integration that monitors RBKC parking suspension emails, geocodes your car location, and alerts you if you're parked in or near a suspended bay.

## Features

- **Binary Sensor**: `binary_sensor.car_in_suspended_bay` with detailed attributes
- **Device Trackers**: Car location + up to 5 active suspension locations (for map display)
- **Auto-notifications**: Alerts via `notify.notify` when suspensions affect your car
- **IMAP Integration**: Automatically processes incoming suspension emails
- **UI Configuration**: Set car location and preferences via Settings UI
- **Dashboard**: Beautiful Lovelace dashboard with status cards and interactive map

## Requirements

- Home Assistant 2025.11.4 or newer
- IMAP integration configured and pointing at your inbox
- RBKC suspension email subscription

## Installation

### Via HACS (Recommended)

1. **Add Custom Repository** (if not in HACS default):
   - Open HACS in Home Assistant
   - Click the three dots menu (⋮) → Custom repositories
   - Add repository URL: `https://github.com/tmonk/rbkc-parking-monitor`
   - Category: Integration
   - Click Add

2. **Install**:
   - Search for "RBKC Parking Suspension Monitor" in HACS
   - Click Download
   - Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/rbkc_parking_monitor` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### 1. Set Up IMAP Integration

Add the IMAP integration and configure it to monitor your inbox:

- **Search**: `SUBJECT "Parking Suspensions Email Alert"`
- This ensures only RBKC suspension emails trigger the integration

### 2. Add Integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "RBKC Parking Suspension Monitor"
3. Enter configuration:
   - **Car Location**: Street address where your car is parked (e.g., "42 Example Street")
   - **Proximity Threshold**: Distance in meters to consider a suspension "nearby" (default: 100m)
   - **Upcoming Window**: Days ahead to check for future suspensions (default: 7 days)
   - **Debug Mode**: Enable verbose logging (optional)

### 3. Subscribe to RBKC Emails

Sign up for RBKC parking suspension email alerts at [rbkc.gov.uk](https://www.rbkc.gov.uk).

## Usage

### Entities Created

**Binary Sensor**: `binary_sensor.car_in_suspended_bay`
- State: `on` if car is at risk now, `off` otherwise
- Attributes:
  - `active_suspensions`: Suspensions affecting your location right now
  - `upcoming_suspensions`: Suspensions starting within your configured window
  - `upcoming_risk`: Boolean indicating upcoming suspensions
  - `all_active_suspensions`: List of all active suspensions (entire borough)
  - `all_upcoming_suspensions`: List of all upcoming suspensions
  - `last_status`: Status of last check
  - `email_data_date`: Timestamp of email data
  - `last_checked`: Last check timestamp

**Device Trackers**:
- `device_tracker.parking_monitor_car`: Your car's location
- `device_tracker.suspension_1` through `suspension_5`: Active suspension locations (for map)

### Service

**`rbkc_parking_monitor.check_parking`**

Manually trigger a parking check.

Parameters:
- `email_body` (optional): Email text to process. If omitted, uses cached data.

Example automation:
```yaml
automation:
  - alias: "Manual Parking Check Button"
    trigger:
      - platform: state
        entity_id: input_button.check_parking_now
    action:
      - service: rbkc_parking_monitor.check_parking
```

### Dashboard

A beautiful dashboard is **automatically registered** when you install the integration.

After installation, look for **"Parking Monitor"** (car icon) in your sidebar. The dashboard includes:

- **Status Cards**: Visual alerts for active/upcoming suspensions
- **Interactive Map**: Shows your car and nearby suspension locations
- **Suspension List**: All active and upcoming suspensions borough-wide
- **Configuration Link**: Quick access to update your car location

If the dashboard doesn't appear in the sidebar after installation:
1. Restart Home Assistant
2. Check Settings → Devices & Services → RBKC Parking Monitor
3. Check Home Assistant logs for dashboard registration errors

### Notifications

The integration automatically sends notifications when:

- **Active suspension**: "🚨 MOVE CAR NOW" (red notification)
- **Upcoming suspension**: "⚠️ Upcoming Suspension" (warning)

Notifications are sent via `notify.notify`. Update your notification service in the integration code if needed.

### Changing Car Location

Two ways to update your car location:

1. **Via UI** (Recommended):
   - Go to **Settings** → **Devices & Services** → **RBKC Parking Monitor** → **Configure**
   - Update "Car Location"
   - Integration will automatically re-check with new location

2. **Via Service Call**:
   ```yaml
   service: rbkc_parking_monitor.check_parking
   data:
     car_location: "New Street Address"
   ```

## How It Works

1. **Email Arrives**: IMAP integration detects new RBKC suspension email
2. **Event Fires**: `imap_content` event triggered
3. **Integration Processes**:
   - Parses email for suspension blocks (street, dates, location)
   - Geocodes car location and suspension addresses via OpenStreetMap Nominatim
   - Calculates distances and checks for matches
   - Updates binary sensor and device trackers
4. **Notifications Sent**: If car is at risk, sends urgent notification
5. **Cached**: Email and geocoding results cached locally for performance

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| Car Location | Town Hall, Hornton Street | Street address where your car is parked |
| Proximity Threshold | 100 meters | Distance to consider a suspension "nearby" |
| Upcoming Window | 7 days | How far ahead to check for suspensions |
| Debug Mode | Off | Enable verbose logging |

## Customization

### Proximity Threshold

If you live on a long street and want tighter matching:
- Lower the proximity threshold (e.g., 50m)
- This reduces false positives from suspensions far down your street

### Upcoming Window

Adjust how far ahead you want warnings:
- Increase for more advance notice (e.g., 14 days)
- Decrease to only see imminent suspensions (e.g., 3 days)

### Notification Service

By default, notifications go to `notify.notify`. To use a different service, you'll need to modify `custom_components/rbkc_parking_monitor/__init__.py`:

```python
await hass.services.async_call(
    "notify",
    "mobile_app_your_phone",  # Change this
    {...}
)
```

## Troubleshooting

### "Cache Empty" Status

**Cause**: No suspension email has been received yet

**Fix**: Forward a recent RBKC suspension email to yourself (the account monitored by IMAP integration)

### Car Location Not Geocoding

**Cause**: Address not found by OpenStreetMap

**Fix**:
- Include a house number in your car location (e.g., "42 Example Street")
- Be specific: "Example Street, Kensington" is better than just "Example Street"

### No Notifications

**Check**:
1. Binary sensor state is `on` (car actually at risk)
2. `notify.notify` service exists and works
3. Check Home Assistant logs for errors

### Integration Not Loading

**Check**:
1. Restart Home Assistant after installation
2. Check `custom_components/rbkc_parking_monitor/` exists
3. Review Home Assistant logs: Settings → System → Logs

## Data & Privacy

- **Email cache**: Stored locally at `/config/parking_email_cache.txt`
- **Geocoding cache**: Stored locally at `/config/parking_geo_cache.json`
- **External API**: OpenStreetMap Nominatim (for geocoding only)
- **No data leaves your Home Assistant** except geocoding requests

## Contributing

Issues and pull requests welcome at [GitHub](https://github.com/tmonk/rbkc-parking-monitor).

## License

Apache License 2.0
