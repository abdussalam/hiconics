"""DataUpdateCoordinator for Hiconics integration."""

import logging
from datetime import datetime, timedelta, timezone
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HiconicsAuthError, HiconicsConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HiconicsDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hiconics data from Solarman API."""

    def __init__(self, hass, api, scan_interval):
        """Initialize coordinator."""
        self.api = api
        self.extra_data = {}
        self.last_tou_read_time: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Hiconics Solarman Coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch live telemetry from Solarman API."""
        try:
            data = await self.api.async_get_current_data()
            if not data:
                raise UpdateFailed("Failed to retrieve valid response from Solarman API.")
            return data
        except HiconicsAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (HiconicsConnectionError, Exception) as err:
            raise UpdateFailed(f"Error fetching Hiconics data: {err}") from err

    def update_extra_data(self, new_data: dict, is_tou: bool = False):
        """Merge newly pulled or updated registers into local state."""
        if isinstance(new_data, dict):
            self.extra_data.update(new_data)
            if is_tou or any(k.startswith("C4") or k.startswith("C5") for k in new_data):
                self.last_tou_read_time = datetime.now(timezone.utc)
            self.async_update_listeners()
