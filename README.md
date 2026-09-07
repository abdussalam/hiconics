# Hiconics Inverter & Battery Home Assistant Integration

A custom Home Assistant integration for **Hiconics Hybrid Inverters (HECS2-S6)** and **Hiconics LFP Batteries** communicating via the **Solarman Cloud API**. 

This integration provides real-time telemetry sensors, device topology mapping, on-demand register fetching, and full UI control over Time-of-Use (TOU) schedules, working modes, and battery configuration profiles.

---

## Features

* **Dual Device Topology:** Separates telemetry into **Hiconics Inverter** and **Hiconics Battery** devices (nested via internal registry IDs).
* **Live Telemetry Polling:** Fetches real-time Volts, Amps, Watts, Energy totals, and Battery State of Charge (SOC) at a configurable interval (default: 10 minutes).
* **Interactive UI Controls:** Modify inverter and battery settings directly from the Home Assistant **Configuration Card**:
  * **6 Time-of-Use (TOU) Slots:** Configurable Start Time, End Time, Mode (*Idle / Self Use*, *Charge*, *Discharge*), Max Charge Amps, Target Max SOC, and Reserve Min SOC.
  * **Peak Usage to Self-Use (`C76`):** Selectable fallback behavior (*Disable*, *Charge: TOU to Self-use*, *Discharge: TOU to Self-use*, *Charge/Discharge: TOU to Self-use*).
  * **Inverter Working Mode (`C1`):** Selectable between `1 - Self Use` and `6 - TOU`.
  * **SOC Profiles:** Configure On-Grid & Off-Grid Min Cut-off SOC, Max Target SOC, and Hysteresis percentages.
  * **System Toggles:** Battery Sleep Mode (`C32`), Grid Charging (`C216`), and Grid Power Limit (`C217`).
* **On-Demand Action Buttons:** One-click buttons on the Inverter Device page to trigger real-time register reads (`Read TOU Settings`, `Read Inverter Mode`, `Read Battery Settings`).
* **Smart Rate Limiting & Token Persistence:** Caches Solarman access tokens in memory, automatically tracking 24-hour expiration timestamps and renewing 5 minutes prior to expiry to conserve API quota.
* **Write Verification Loop:** Automatically polls hardware registers 15 seconds after a write command to confirm that the inverter accepted the parameter updates.

---

## Prerequisites

Before installing, obtain your Solarman Cloud API credentials:
1. **Solarman Account Credentials:** Your account `Username` and `Password`.
2. **App Credentials:** `App ID` (default provided) and `App Secret` from your Solarman developer account.
3. **Hardware Identifiers:** Your Inverter **Device Serial Number (SN)** and **Device ID**.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **Home Assistant** and navigate to **HACS** > **Integrations**.
2. Click the **three vertical dots** in the top-right corner and select **Custom repositories**.
3. Add your repository URL:
   * **Repository:** `https://github.com/abdussalam/hiconics`
   * **Category:** `Integration`
4. Click **Add**.
5. Search for **Hiconics Solarman Integration** in HACS and click **Download**.
6. **Restart Home Assistant**.

---

### Method 2: Manual Installation

1. Download the latest release from the repository.
2. Copy the `custom_components/hiconics/` directory into your Home Assistant `/config/custom_components/` directory:
   ```text
   config/
   └── custom_components/
       └── hiconics/
           ├── __init__.py
           ├── api.py
           ├── button.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── manifest.json
           ├── number.py
           ├── select.py
           ├── sensor.py
           ├── services.yaml
           ├── switch.py
           ├── text.py
           └── strings.json
   ```
3. **Restart Home Assistant**.

---

## Configuration

### Initial Setup

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Hiconics**.
3. Enter your Solarman credentials and device identifiers:
   * **Username:** Your Solarman account email/username.
   * **Password:** Your Solarman account password.
   * **App Secret:** Your Solarman developer API secret.
   * **Device SN:** Inverter Serial Number.
   * **Device ID:** Inverter Device ID.
   * **Polling Interval:** Seconds between telemetry polls (default: `600`).
4. Click **Submit**.

### Editing Settings Later

You can change your credentials or polling interval at any time:
1. Go to **Settings** > **Devices & Services** > **Hiconics**.
2. Click **Configure**.
3. Adjust the values in the pop-up modal and click **Submit**.

---

## Device Overview & Control Mapping

### Interactive Controls (Configuration Card)

| Group | Parameter | Register | Options / Range |
| :--- | :--- | :--- | :--- |
| **Working Mode** | Inverter Working Mode | `C1` | `1 - Self Use`, `6 - TOU` |
| **Peak Usage** | TOU - Peak Usage to Self-Use | `C76` | `0 - Disable`, `1 - Charge: TOU to Self-use`, `2 - Discharge: TOU to Self-use`, `3 - Charge/Discharge: TOU to Self-use` |
| **TOU Slots 1–6** | Start Time | `C40`, `C46`, `C52`, ... | Format `HH:MM` (e.g. `01:30`) |
| | End Time | `C41`, `C47`, `C53`, ... | Format `HH:MM` (e.g. `05:00`) |
| | Mode | `C42`, `C48`, `C54`, ... | `0 - Idle / Self Use`, `1 - Charge`, `2 - Discharge` |
| | Max Charge Amps | `C43`, `C49`, `C55`, ... | `0.0` to `25.0` A |
| | Max Target SOC | `C44`, `C50`, `C56`, ... | `50` to `100` % |
| | Min Reserve SOC | `C45`, `C51`, `C57`, ... | `0` to `100` % |
| **On-Grid Profile**| On-Grid Min Cut-off SOC | `C33` | `0` to `50` % |
| | On-Grid Max Target SOC | `C34` | `50` to `100` % |
| | On-Grid Hysteresis | `C35` | `0` to `30` % |
| **Off-Grid Profile**| Off-Grid Min Cut-off SOC | `C36` | `0` to `50` % |
| | Off-Grid Max Target SOC | `C37` | `50` to `100` % |
| | Off-Grid Hysteresis | `C38` | `0` to `30` % |
| **System Controls**| Battery Sleep Mode | `C32` | `ON` (1) / `OFF` (0) |
| | Grid Charging | `C216` | `ON` (1) / `OFF` (0) |
| | Grid Power Limit | `C217` | `0` to `15000` W |

---

## Custom Actions / Services

The integration registers four action calls for use in scripts or dashboard automations:

### 1. `hiconics.set_tou_slot`
Applies a full parameter set to a specific TOU schedule slot.

```yaml
action: hiconics.set_tou_slot
data:
  slot: 1
  start_time: "0130"
  end_time: "0500"
  mode: "1" # 0: Idle / Self Use, 1: Charge, 2: Discharge
  max_amps: 25
  max_soc: 100
  min_soc: 18
```

### 2. `hiconics.set_inverter_mode`
Changes the primary working mode of the inverter.

```yaml
action: hiconics.set_inverter_mode
data:
  mode: "6" # 1: Self Use, 6: TOU
```

### 3. `hiconics.read_settings`
Queries the inverter for on-demand register settings.

```yaml
action: hiconics.read_settings
data:
  type: "tou" # Options: "mode", "battery", "tou"
```

### 4. `hiconics.send_command`
Sends raw parameter payloads to custom Solarman command codes.

```yaml
action: hiconics.send_command
data:
  code: "s_A8"
  operation_type: 5
  input_param:
    C40:
      v: "0130"
```

---

## Troubleshooting & Debugging

If you encounter issues reading registers or communicating with the Solarman API, enable debug logging in your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.hiconics: debug
```

Inspect the logs under **Settings** > **System** > **Logs** to trace order ID creation, status polling attempts, and API responses.
