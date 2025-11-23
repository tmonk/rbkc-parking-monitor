# RBKC Parking Suspension Monitor 🚗

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration) [![version](https://img.shields.io/github/v/release/tmonk/rbkc-parking-monitor)](https://github.com/tmonk/rbkc-parking-monitor/releases)

**Avoid parking fines in Kensington and Chelsea.** This integration monitors official RBKC suspension emails and alerts you if your car is parked in a suspended bay.

## 🚀 Quick Start

1.  **Install**: Search for "RBKC Parking" in HACS and install.
2.  **Set up IMAP**: You *must first* configure the standard Home Assistant **IMAP** integration (separate from this integration) to monitor the email account where you receive RBKC suspension alerts.
    *   **Crucially**: In your IMAP integration setup, ensure the 'IMAP search' field is configured to look for emails with the subject: `SUBJECT "Parking Suspensions Email Alert"`. This integration will then listen for events from your IMAP setup that match these criteria.
    *   *Tip: Forward a recent suspension email to this inbox to kickstart the system immediately.*
3.  **Add Monitor**: Go to **Settings > Devices & Services**, add **RBKC Parking Monitor**.
    *   Enter your **Car Location** (e.g., "10 High Street, W8").
    *   *Optional:* Adjust the proximity threshold (default 100m).

## 📱 Features
*   **Auto-Dashboard**: A "Parking Monitor" dashboard is automatically added to your sidebar.
*   **Smart Alerts**:
    *   🚨 **Active Risk**: You are currently in a suspended bay.
    *   ⚠️ **Upcoming**: A suspension starts nearby soon (default 7 days).
*   **Map**: Visualizes your car and active suspensions using OpenStreetMap geocoding.

## 🔧 Technical Reference

| Entity / Service | ID | Description |
| :--- | :--- | :--- |
| **Status Sensor** | `binary_sensor.rbkc_parking_monitor_car_in_suspended_bay` | `on` = At Risk. Attributes contain suspension lists. |
| **Car Tracker** | `device_tracker.rbkc_parking_monitor_car` | Tracks your configured parking location. |
| **Suspensions** | `device_tracker.rbkc_parking_monitor_suspension_X` | Geocoded locations of active suspensions (1-5). |
| **Check Service** | `rbkc_parking_monitor.check_parking` | Manually trigger a check (accepts `email_body`). |
| **Update Service** | `rbkc_parking_monitor.set_car_location` | Update car location via automation. |

## ❓ Troubleshooting
*   **"Cache Empty"**: The system hasn't seen an email yet. Forward a suspension email to your monitored inbox.
*   **Wrong Location**: Nominatim geocoding is good but not perfect. Try adding the full postcode (e.g., "W8 7NX").

## ⚠️ Disclaimer
This tool is for assistance only. **Always check physical street signage** before leaving your car. The developers are not responsible for any Parking Charge Notices (PCNs) incurred.