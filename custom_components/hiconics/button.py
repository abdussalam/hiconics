"""Button platform for Hiconics integration."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = [
        HiconicsPullTouButton(coordinator, api, entry),
        HiconicsPullInverterModeButton(coordinator, api, entry),
        HiconicsPullBatteryButton(coordinator, api, entry),
        HiconicsApplyAllTouButton(coordinator, api, entry),
    ]

    async_add_entities(entities)


class HiconicsPullTouButton(CoordinatorEntity, ButtonEntity):
    """Button to pull TOU settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull TOU Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_tou"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read TOU settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "tou"}
        )


class HiconicsPullInverterModeButton(CoordinatorEntity, ButtonEntity):
    """Button to pull Inverter Mode settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull Inverter Mode"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_mode"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read Inverter Mode settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "mode"}
        )


class HiconicsPullBatteryButton(CoordinatorEntity, ButtonEntity):
    """Button to pull Battery settings from the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Pull Battery Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_pull_battery"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Read Battery settings from API."""
        await self.hass.services.async_call(
            DOMAIN, "read_settings", {"entry_id": self.entry.entry_id, "type": "battery"}
        )


class HiconicsApplyAllTouButton(CoordinatorEntity, ButtonEntity):
    """Button to push all staged TOU slot changes together as a single unit to the inverter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-upload"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Apply TOU Settings"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self.entry = entry
        self._attr_unique_id = f"hiconics_{entry.entry_id}_btn_apply_all_tou"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_inverter")},
            "manufacturer": "Hiconics",
            "model": "HECS2-S6",
            "name": "Hiconics Inverter",
        }

    async def async_press(self) -> None:
        """Collect all 6 slots (C40 to C75) from local staged state and push them all in one call."""
        # Ensure all 36 TOU registers (Slots 1-6) are present in extra_data
        all_tou_keys = [f"C{reg}" for reg in range(40, 76)]
        if not all(k in self.coordinator.extra_data for k in all_tou_keys):
            raise HomeAssistantError("Cannot apply settings: Not all TOU registers have been read yet. Please click 'Pull TOU Settings' first.")

        # Build the full combined parameter dictionary for all 6 slots
        params = {}
        for reg in range(40, 76):
            key = f"C{reg}"
            val = str(self.coordinator.extra_data.get(key, "0"))
            # Clean and format each value properly
            val_str = val.replace(":", "").strip()
            if "-" in val_str:
                val_str = val_str.split("-")[0].strip()
            if val_str.replace(".", "", 1).isdigit():
                val_str = str(int(float(val_str)))
            params[key] = {"v": val_str.zfill(4) if reg % 6 in (0, 1) else val_str}

        _LOGGER.debug("Sending all TOU slots s_A8 payload: %s", params)
        try:
            await self.api.async_send_command(code="s_A8", operation_type=5, input_param=params)
        except Exception as err:
            if "OR_THERE_ARE_ORDER_BEING_SENT" in str(err):
                raise HomeAssistantError("Inverter is busy processing another command. Please try again in 10 seconds.")
            raise

        # Update coordinator state with the successfully applied values
        self.coordinator.update_extra_data({k: v["v"] for k, v in params.items()}, is_tou=True)
