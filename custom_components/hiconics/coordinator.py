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
        super().__init__(
            hass,
            _LOGGER,
            name="Hiconics Solarman Coordinator",
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> dict:
        try:
            res = await self.api.async_get_device_data()
            if res.get("success") in (0, "0"):
                raise UpdateFailed(f"Solarman API returned error: {res}")
            return res
        except Exception as err:
            raise UpdateFailed(f"Error fetching Hiconics data: {err}") from err
