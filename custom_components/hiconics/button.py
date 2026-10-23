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
    """Button to push all staged TOU slots to the inverter using strict cache validation (no fallbacks)."""

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
        """Iterate through all 6 slots and push each slot block via set_tou_slot service after strict validation."""
        for slot in range(1, 7):
            base_reg = 40 + ((slot - 1) * 6)
            required_keys = [f"C{base_reg + i}" for i in range(6)]

            # STRICT COMPLIANCE: Refuse write if any register in the block has not been read yet.
            if not self.coordinator.extra_data or not all(k in self.coordinator.extra_data for k in required_keys):
                raise HomeAssistantError(
                    f"Cannot apply settings: Slot {slot} register block has not been read yet. Please click 'Pull TOU Settings' first."
                )

            def get_clean_reg(offset: int) -> str:
                key = f"C{base_reg + offset}"
                val = self.coordinator.extra_data.get(key)
                if val is None or str(val).strip() == "" or str(val).lower() == "none":
                    raise HomeAssistantError(f"Cannot apply settings: Register {key} is empty or unread.")
                val_str = str(val).replace(":", "").strip()
                if "-" in val_str:
                    val_str = val_str.split("-")[0].strip()
                if val_str.replace(".", "", 1).isdigit():
                    val_str = str(int(float(val_str)))
                return val_str

            payload = {
                "entry_id": self.entry.entry_id,
                "slot": slot,
                "start_time": get_clean_reg(0).zfill(4),
                "end_time": get_clean_reg(1).zfill(4),
                "mode": get_clean_reg(2),
                "max_amps": get_clean_reg(3),
                "max_soc": get_clean_reg(4),
                "min_soc": get_clean_reg(5),
            }

            await self.hass.services.async_call(DOMAIN, "set_tou_slot", payload)
            await asyncio.sleep(2)
