"""Select platform for Hiconics TOU mode and Inverter mode configuration."""

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
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

    # Create Editable Start and End time selectors for TOU slots 1-6
    for slot in range(1, 7):
        entities.append(HiconicsTOUTimeSelect(coordinator, entry, slot, is_start=True))
        entities.append(HiconicsTOUTimeSelect(coordinator, entry, slot, is_start=False))    
    
    async_add_entities(entities)


class HiconicsInverterModeSelect(CoordinatorEntity, SelectEntity):
    """Interactive select control for Inverter Working Mode (C1)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Inverter - Working Mode"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_C1"
        self._attr_options = INVERTER_MODE_OPTIONS

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get("C1", ""))
        return INVERTER_MODE_MAP_TO_TXT.get(raw, None)

    async def async_select_option(self, option: str) -> None:
        num_val = INVERTER_MODE_MAP_TO_NUM.get(option, "1")
        params = {"C1": {"v": num_val}}
        _LOGGER.info("Updating Inverter Working Mode (C1) to %s (%s)...", option, num_val)
        await self.api.async_send_command(code="s_A1", operation_type=5, input_param=params)
        self.coordinator.update_extra_data({"C1": num_val})


class HiconicsPeakUsageSelect(CoordinatorEntity, SelectEntity):
    """Interactive select control for Peak Usage TOU Settings (C76)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "TOU - Peak Usage to Self-Use"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_C76"
        self._attr_options = PEAK_USAGE_OPTIONS

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get("C76", ""))
        return PEAK_USAGE_MAP_TO_TXT.get(raw, None)

    async def async_select_option(self, option: str) -> None:
        num_val = PEAK_USAGE_MAP_TO_NUM.get(option, "0")
        params = {"C76": {"v": num_val}}
        _LOGGER.info("Updating C76 Peak Usage Mode to %s (%s)...", option, num_val)
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data({"C76": num_val})


class HiconicsTouModeSelect(CoordinatorEntity, SelectEntity):
    """Interactive mode select control for TOU slots."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, api, entry, slot: int, reg_key: str):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._slot = slot
        self._reg_key = reg_key
        self._attr_name = f"Slot {slot} - C. Mode"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_{reg_key}"
        self._attr_options = TOU_MODE_OPTIONS

    @property
    def device_info(self):
        inverter_id = (DOMAIN, f"{self.entry.entry_id}_inverter")
        return {
            "identifiers": {inverter_id},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        raw = str(self.coordinator.extra_data.get(self._reg_key, ""))
        return TOU_MODE_MAP_TO_TXT.get(raw, None)

    async def async_select_option(self, option: str) -> None:
        num_val = TOU_MODE_MAP_TO_NUM.get(option, "0")
        base_reg = 40 + ((self._slot - 1) * 6)

        current_map = {
            f"C{base_reg}": self.coordinator.extra_data.get(f"C{base_reg}", "0000"),
            f"C{base_reg+1}": self.coordinator.extra_data.get(f"C{base_reg+1}", "0000"),
            f"C{base_reg+2}": self.coordinator.extra_data.get(f"C{base_reg+2}", "0"),
            f"C{base_reg+3}": self.coordinator.extra_data.get(f"C{base_reg+3}", "25"),
            f"C{base_reg+4}": self.coordinator.extra_data.get(f"C{base_reg+4}", "100"),
            f"C{base_reg+5}": self.coordinator.extra_data.get(f"C{base_reg+5}", "18"),
        }
        current_map[self._reg_key] = num_val
        params = {k: {"v": v} for k, v in current_map.items()}
        await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        self.coordinator.update_extra_data(current_map)

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class HiconicsTOUTimeSelect(CoordinatorEntity, SelectEntity):
    """Dropdown selector for TOU Start and End Times."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-edit-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, slot: int, is_start: bool):
        super().__init__(coordinator)
        self.entry = entry
        self._slot = slot
        self._is_start = is_start

        base_reg = 40 + ((slot - 1) * 6)
        self._reg = f"C{base_reg}" if is_start else f"C{base_reg + 1}"

        time_type = "Start" if is_start else "End"
        self._attr_name = f"TOU Slot {slot} {time_type} Time"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_tou_select_{slot}_{time_type.lower()}"
        
        # Generate options: 00:00, 00:15, 00:30 ... 23:45
        self._attr_options = [
            f"{str(h).zfill(2)}:{str(m).zfill(2)}" 
            for h in range(24) for m in (0, 15, 30, 45)
        ]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self):
        """Get current time from inverter registers."""
        extra_data = getattr(self.coordinator, "extra_data", {})
        raw_time = extra_data.get(self._reg)
        if raw_time and str(raw_time) != "None":
            val = str(raw_time).zfill(4)
            if len(val) == 4:
                return f"{val[:2]}:{val[2:]}"
        return "00:00"

    async def async_select_option(self, option: str):
        """Send the updated time to the inverter."""
        extra = getattr(self.coordinator, "extra_data", {})
        base_reg = 40 + ((self._slot - 1) * 6)

        # Helper to fetch current values for the rest of the slot
        def get_val(offset, default): 
            return extra.get(f"C{base_reg + offset}", default)

        # Compile the 6-register payload
        start = option if self._is_start else get_val(0, "0000")
        end = option if not self._is_start else get_val(1, "0000")
        
        payload = {
            "slot": self._slot,
            "start_time": start,
            "end_time": end,
            "mode": int(get_val(2, 0)),
            "max_amps": float(get_val(3, 25)),
            "max_soc": float(get_val(4, 100)),
            "min_soc": float(get_val(5, 18))
        }

        # Call the service we registered in __init__.py
        await self.hass.services.async_call(DOMAIN, "set_tou_slot", payload)
        
        # Optimistically update the UI immediately
        self.coordinator.extra_data[self._reg] = option.replace(":", "")
        self.async_write_ha_state()

