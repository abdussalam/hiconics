"""Select platform for Hiconics TOU modes."""

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TOU_MODE_OPTIONS = ["0 - Stop", "1 - Charge", "2 - Discharge"]
TOU_MODE_MAP_TO_NUM = {"0 - Stop": "0", "1 - Charge": "1", "2 - Discharge": "2"}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for slot in range(1, 7):
        entities.append(HiconicsTouModeSelect(coordinator, entry, slot))

    async_add_entities(entities)


class HiconicsTouModeSelect(CoordinatorEntity, SelectEntity):
    """Select dropdown entity for TOU Slot Modes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:lightning-bolt-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = TOU_MODE_OPTIONS

    def __init__(self, coordinator, entry, slot: int):
        """Initialize select entity."""
        super().__init__(coordinator)
        self.entry = entry
        self._slot = slot
        base_reg = 40 + ((slot - 1) * 6)
        self._reg_key = f"C{base_reg + 2}"
        self._attr_name = f"Slot {slot} - C. Mode"
        self._attr_unique_id = f"hiconics_{entry.entry_id}_sel_tou_mode_{slot}"

    @property
    def device_info(self):
        """Return inverter device info."""
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    @property
    def current_option(self) -> str | None:
        """Return current mode option from extra_data."""
        val = self.coordinator.extra_data.get(self._reg_key)
        if val is None:
            return None
        val_str = str(val).split("-")[0].strip() if "-" in str(val) else str(val).strip()
        for opt in TOU_MODE_OPTIONS:
            if opt.startswith(val_str):
                return opt
        return None

    async def async_select_option(self, option: str) -> None:
        """Stage option locally without dispatching an API call."""
        base_reg = 40 + ((self._slot - 1) * 6)
        required_keys = [f"C{base_reg + i}" for i in range(6)]

        if not all(k in self.coordinator.extra_data for k in required_keys):
            raise HomeAssistantError("Cannot stage value: TOU register block has not been read from inverter yet.")

        num_val = TOU_MODE_MAP_TO_NUM.get(option, option.split("-")[0].strip())

        # Stage change in coordinator extra_data locally
        self.coordinator.extra_data[self._reg_key] = str(num_val)
        self.async_write_ha_state()
