"""Sensor platform for Hiconics inverter and battery."""

import logging
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DIAGNOSTIC_KEYWORDS = [
    "status", "state", "mode", "alarm", "warning", "error", "version",
    "sn", "supplier", "record", "control", "type", "clusters", "parm",
    "factor", "system time", "rated", "capacity", "setting", "limit",
    "sampling sections", "fault level", "flag"
]

BATTERY_KEYWORDS = ["battery", "inline", "parallel", "charg", "soc", "b_c", "capacity"]


def is_battery_sensor(key: str, name: str) -> bool:
    """Determine if a key or name corresponds to a battery sensor."""
    lower = f"{key} {name or ''}".lower()
    return any(w in lower for w in BATTERY_KEYWORDS)


def get_entity_category(key: str, name: str):
    """Categorize diagnostic sensors automatically."""
    lower = f"{key} {name or ''}".lower()
    if any(w in lower for w in DIAGNOSTIC_KEYWORDS):
        return EntityCategory.DIAGNOSTIC
    return None


def normalize_unit(unit: str) -> str:
    """Normalize unit string formats for Home Assistant compatibility."""
    if not unit:
        return None
    units_map = {"KW": "kW", "HZ": "Hz", "℃": "°C", "Var": "var"}
    return units_map.get(unit, unit)


def get_device_class(unit: str):
    """Map normalized unit to SensorDeviceClass."""
    mapping = {
        "V": SensorDeviceClass.VOLTAGE,
        "mV": SensorDeviceClass.VOLTAGE,
        "A": SensorDeviceClass.CURRENT,
        "W": SensorDeviceClass.POWER,
        "kW": SensorDeviceClass.POWER,
        "kvar": SensorDeviceClass.REACTIVE_POWER,
        "var": SensorDeviceClass.REACTIVE_POWER,
        "kVA": SensorDeviceClass.APPARENT_POWER,
        "kWh": SensorDeviceClass.ENERGY,
        "%": SensorDeviceClass.BATTERY,
        "Hz": SensorDeviceClass.FREQUENCY,
        "°C": SensorDeviceClass.TEMPERATURE,
        "s": SensorDeviceClass.DURATION,
    }
    return mapping.get(unit)


def get_state_class(unit: str, key: str, name: str):
    """Determine appropriate state class based on unit and name."""
    lower = f"{key} {name or ''}".lower()
    if unit in ["w", "kw", "kva", "kvar", "var", "v", "mv", "a", "hz", "%", "°c", "s"]:
        return SensorStateClass.MEASUREMENT
    if unit == "kwh" and "total" in lower:
        return SensorStateClass.TOTAL_INCREASING
    if unit == "kwh":
        return SensorStateClass.TOTAL
    return None


def get_clean_entity_name(raw_name: str, key: str, is_battery: bool) -> str:
    """Clean up prefix redundancies from raw entity names."""
    name = raw_name or key
    clean = name.strip()
    prefixes = ["hiconics battery ", "hiconics inverter ", "hiconics "]
    for prefix in prefixes:
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):].strip()
            break

    if is_battery and clean.lower().startswith("battery "):
        clean = clean[8:].strip()
    elif not is_battery and clean.lower().startswith("inverter "):
        clean = clean[9:].strip()

    return (clean or name).strip()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics sensor entities dynamically."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known_keys = set()

    def _create_entities():
        new_entities = []

        data = coordinator.data or {}
        data_list = data.get("dataList", []) if isinstance(data, dict) else []

        # 1. Standard telemetry sensors from Solarman API dataList
        for item in data_list:
            key = item.get("key")
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            new_entities.append(HiconicsSensor(coordinator, entry, item))

        # 2. Dynamic extra registers from on-demand reads
        extra_data = getattr(coordinator, "extra_data", {})
        controlled_keys = {"C1", "C32", "C33", "C34", "C35", "C36", "C37", "C38", "C216", "C217"}

        for key in extra_data:
            if not key or key in known_keys or key in controlled_keys:
                continue
            if key.startswith("C") and key[1:].isdigit() and 40 <= int(key[1:]) <= 76:
                continue

            known_keys.add(key)
            new_entities.append(HiconicsExtraSensor(coordinator, entry, key))

        # 3. Diagnostic Timestamp Sensor for Last TOU Read Time
        if "last_tou_read" not in known_keys:
            known_keys.add("last_tou_read")
            new_entities.append(HiconicsLastTouReadSensor(coordinator, entry))

        # 4. Derived RTC Timestamp Sensor
        if "rtc_timestamp" not in known_keys:
            known_keys.add("rtc_timestamp")
            new_entities.append(HiconicsRtcTimestampSensor(coordinator, entry))

        if new_entities:
            async_add_entities(new_entities)

    _create_entities()
    entry.async_on_unload(coordinator.async_add_listener(_create_entities))


class HiconicsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hiconics Telemetry Sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, item):
        """Initialize telemetry sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._key = item.get("key")
        raw_name = item.get("name") or self._key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_{self._key}"
        self._is_battery = is_battery_sensor(self._key, raw_name)
        self._attr_name = get_clean_entity_name(raw_name, self._key, self._is_battery)

        unit = normalize_unit(item.get("unit"))
        if not unit and any(x in raw_name.lower() for x in ["soc", "soh"]):
            unit = "%"
        self._attr_native_unit_of_measurement = unit
        if unit:
            self._attr_device_class = get_device_class(unit)
            self._attr_state_class = get_state_class(unit.lower(), self._key, raw_name)
        self._attr_entity_category = get_entity_category(self._key, raw_name)

    @property
    def device_info(self):
        """Link sensor to either Battery or Inverter device in Home Assistant."""
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        if self._is_battery:
            via_device_id = dr.async_get_device_id_by_identifier(
                self.hass, inverter_id, config_entry_id=self.entry.entry_id
            )
            return {
                "identifiers": {(DOMAIN, f"{self.entry.entry_id}_battery")},
                "manufacturer": "Hiconics",
                "model": "LFP Battery",
                "name": "Hiconics Battery",
                "via_device_id": via_device_id,
            }
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self):
        """Extract sensor value from current telemetry data."""
        if not self.coordinator.data:
            return None
        data_list = self.coordinator.data.get("dataList", []) if isinstance(self.coordinator.data, dict) else []
        for item in data_list:
            if item.get("key") == self._key:
                val = item.get("value")
                if val is None or val == "":
                    return None
                try:
                    return float(val) if "." in str(val) else int(val)
                except ValueError:
                    return str(val)
        return None


class HiconicsExtraSensor(CoordinatorEntity, SensorEntity):
    """Representation of an on-demand pulled Hiconics sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str):
        """Initialize extra register sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"hiconics_{entry.entry_id}_extra_{key}"
        self._is_battery = False
        self._attr_name = get_clean_entity_name(key, key, self._is_battery)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        """Return inverter device info."""
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self):
        """Get value from extra_data dictionary."""
        extra = getattr(self.coordinator, "extra_data", {})
        return extra.get(self._key)


class HiconicsLastTouReadSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor displaying UTC timestamp of last TOU read."""

    _attr_has_entity_name = True
    _attr_name = "Last TOU Read Time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, entry):
        """Initialize diagnostic timestamp sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sensor_last_tou_read"

    @property
    def device_info(self):
        """Return inverter device info."""
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> datetime | None:
        """Return UTC datetime timestamp recorded in coordinator."""
        return getattr(self.coordinator, "last_tou_read_time", None)


class HiconicsRtcTimestampSensor(CoordinatorEntity, SensorEntity):
    """Derived sensor showing the parsed RTC timestamp without day-of-week suffix."""

    _attr_has_entity_name = True
    _attr_name = "RTC Timestamp"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, entry):
        """Initialize RTC Timestamp sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sensor_rtc_timestamp"

    @property
    def device_info(self):
        """Return inverter device info."""
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def native_value(self) -> datetime | None:
        """Find the raw RTC Time value from dataList and strip day-of-week suffix."""
        raw_val = None
        
        if self.coordinator.data:
            data_list = self.coordinator.data.get("dataList", []) if isinstance(self.coordinator.data, dict) else []
            for item in data_list:
                name = str(item.get("name", "")).lower()
                key = str(item.get("key", "")).lower()
                if "rtc time" in name or "rtc" in key or "system time" in name:
                    raw_val = item.get("value")
                    break

        if not raw_val:
            extra = getattr(self.coordinator, "extra_data", {})
            for k, v in extra.items():
                if "rtc" in k.lower():
                    raw_val = v
                    break

        if not raw_val:
            return None

        try:
            # Strip day of week suffix (e.g., " -5")
            time_str = str(raw_val).split("-")[0].strip()
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as err:
            _LOGGER.debug("Failed to parse RTC time value '%s': %s", raw_val, err)
            return None
