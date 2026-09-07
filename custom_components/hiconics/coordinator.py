"""DataUpdateCoordinator for Hiconics."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolarmanAPIClient

_LOGGER = logging.getLogger(__name__)


class HiconicsDataCoordinator(DataUpdateCoordinator):
    """Coordinator to poll Solarman device data periodically."""

    def __init__(self, hass: HomeAssistant, api: SolarmanAPIClient, update_interval: int):
        self.api = api
        self.extra_data = {}  # Store on-demand pulled registers (TOU, mode settings, etc.)
        super().__init__(
            hass,
            _LOGGER,
            name="Hiconics Solarman Coordinator",
            update_interval=timedelta(seconds=update_interval),
        )

    def update_extra_data(self, new_data: dict):
        """Update on-demand registers and notify listeners to add/update entities."""
        flat_data = {}
        for k, v in new_data.items():
            if isinstance(v, dict) and "v" in v:
                flat_data[k] = str(v["v"])
            else:
                flat_data[k] = str(v)
        self.extra_data.update(flat_data)
        # Notify Home Assistant entity listeners
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict:
        try:
            res = await self.api.async_get_current_data()
            if res.get("success") in (0, "0"):
                raise UpdateFailed(f"Solarman API returned error: {res}")
            return res
        except Exception as err:
            raise UpdateFailed(f"Error fetching Hiconics data: {err}") from err
