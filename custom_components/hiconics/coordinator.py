"""DataUpdateCoordinator for Hiconics integration."""

import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class HiconicsDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hiconics data from Solarman API."""

    def __init__(self, hass, api, scan_interval):
        """Initialize coordinator."""
        self.api = api
        self.extra_data = {}

        super().__init__(
            hass,
            _LOGGER,
            name="Hiconics Solarman Coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch live telemetry from Solarman API."""
        try:
            # Make sure this line calls async_get_current_data(), NOT async_get_device_data()
            data = await self.api.async_get_current_data()
            if not data:
                raise UpdateFailed("Failed to retrieve valid response from Solarman API.")
            return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching Hiconics data: {err}") from err

    def update_extra_data(self, new_data: dict):
        """Merge newly pulled or updated registers into local state."""
        if isinstance(new_data, dict):
            self.extra_data.update(new_data)
            self.async_update_listeners()
