"""Select platform for Hiconics TOU mode and Inverter mode configuration."""

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TOU_MODE_OPTIONS = [
    "0 - Idle / Self Use",
    "1 - Charge",
    "2 - Discharge",
]

TOU_MODE_MAP_TO_NUM = {
    "0 - Idle / Self Use": "0",
    "1 - Charge": "1",
    "2 - Discharge": "2",
}

TOU_MODE_MAP_TO_TXT = {
    "0": "0 - Idle / Self Use",
    "1": "1 - Charge",
    "2": "2 - Discharge",
}

INVERTER_MODE_OPTIONS = [
    "1 - Self Use",
    "6 - TOU",
]

INVERTER_MODE_MAP_TO_NUM = {
    "1 - Self Use": "1",
    "6 - TOU": "6",
}

INVERTER_MODE_MAP_TO_TXT = {
    "1": "1 - Self Use",
    "6": "6 - TOU",
}

PEAK_USAGE_OPTIONS = [
    "0 - Disable",
    "1 - Charge: TOU to Self-use",
    "2 - Discharge: TOU to Self-use",
    "3 - Charge/Discharge: TOU to Self-use",
]

PEAK_USAGE_MAP_TO_NUM = {
    "0 - Disable": "0",
    "1 - Charge: TOU to Self-use": "1",
    "2 - Discharge: TOU to Self-use": "2",
    "3 - Charge/Discharge: TOU to Self-use": "3",
}

PEAK_USAGE_MAP_TO_TXT = {v: k for k, v in PEAK_USAGE_MAP_TO_NUM.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = [
        HiconicsInverterModeSelect(coordinator, api, entry),
        HiconicsPeakUsageSelect(coordinator, api, entry)
    ]

    for slot in range(1, 7):
        base_reg = 40 + ((slot - 1) * 6)
        entities.append(HiconicsTouModeSelect(coordinator, api, entry, slot, f"C{base_reg+2}"))
    
    async_add_entities(entities)


class HiconicsInverterModeSelect(CoordinatorEntity, SelectEntity):
    """Interactive select control for Inverter Working Mode (C1)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Inverter - Working Mode"
    _attr_options = INVERTER_MODE_OPTIONS

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_C1"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get("C1", ""))
        val_str = raw.split("-")[0].strip() if "-" in raw else raw.strip()
        return INVERTER_MODE_MAP_TO_TXT.get(val_str, None)

    async def async_select_option(self, option: str) -> None:
        if "C1" not in self.coordinator.extra_data:
            raise HomeAssistantError("Cannot write to inverter: Mode register C1 has not been read yet.")
        num_val = INVERTER_MODE_MAP_TO_NUM.get(option, option.split("-")[0].strip())
        payload = {"entry_id": self.entry.entry_id, "mode": num_val}
        await self.hass.services.async_call(DOMAIN, "set_inverter_mode", payload)


class HiconicsPeakUsageSelect(CoordinatorEntity, SelectEntity):
    """Interactive select control for Peak Usage TOU Settings (C76)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "TOU - Peak Usage to Self-Use"
    _attr_options = PEAK_USAGE_OPTIONS

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_C76"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get("C76", ""))
        val_str = raw.split("-")[0].strip() if "-" in raw else raw.strip()
        return PEAK_USAGE_MAP_TO_TXT.get(val_str, None)

    async def async_select_option(self, option: str) -> None:
        if "C76" not in self.coordinator.extra_data:
            raise HomeAssistantError("Cannot write to inverter: Peak usage register C76 has not been read yet.")
        num_val = PEAK_USAGE_MAP_TO_NUM.get(option, "0")
        self.coordinator.extra_data["C76"] = num_val
        self.async_write_ha_state()


class HiconicsTouModeSelect(CoordinatorEntity, SelectEntity):
    """Interactive mode select control for TOU slots (local staging)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = TOU_MODE_OPTIONS

    def __init__(self, coordinator, api, entry, slot: int, reg_key: str):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        self._attr_name = f"Slot {slot} - C. Mode"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_{reg_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get(self._reg_key, ""))
        val_str = raw.split("-")[0].strip() if "-" in raw else raw.strip()
        return TOU_MODE_MAP_TO_TXT.get(val_str, None)

    async def async_select_option(self, option: str) -> None:
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]
        
        # STRICT COMPLIANCE: Refuse staging if the slot block has not been read yet.
        if not self.coordinator.extra_data or not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot stage value: TOU register block has not been read yet. Please click 'Pull TOU Settings' first.")

        num_val = TOU_MODE_MAP_TO_NUM.get(option, option.split("-")[0].strip())

        # Stage change locally in coordinator extra_data without triggering immediate network calls
        self.coordinator.extra_data[self._reg_key] = str(num_val)
        self.async_write_ha_state()
