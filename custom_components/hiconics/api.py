"""Solarman Cloud API client for Hiconics."""

import asyncio
import hashlib
import logging
import time

from .const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_DEVICE_SN,
    CONF_DEVICE_ID,
)

_LOGGER = logging.getLogger(__name__)

URL_TOKEN = "https://globalapi.solarmanpv.com/account/v1.0/token"
URL_DEVICE = "https://globalapi.solarmanpv.com/device/v1.0/currentData"
URL_COMMAND = "https://globalapi.solarmanpv.com/device/v1.0/command"


class SolarmanAPIClient:
    """API Client to interface with Solarman Cloud."""

    def __init__(self, session, config):
        self.session = session
        self.username = config.get(CONF_USERNAME, "")
        self.password = config.get(CONF_PASSWORD, "")
        self.app_id = config.get(CONF_APP_ID, "")
        self.app_secret = config.get(CONF_APP_SECRET, "")
        self.device_sn = config.get(CONF_DEVICE_SN, "")
        self.device_id = config.get(CONF_DEVICE_ID, "")

        self._token = None
        self._token_expires_at = 0        

    async def async_get_token(self):
        """Retrieve or return cached token."""
        now = time.time()
        if self._token and now < (self._token_expires_at - 300):
            return self._token

        url = f"{URL_TOKEN}?appId={self.app_id}&language=en"
        payload = {
            "appSecret": self.app_secret,
            "email": self.username,
            "password": self.password,
        }

        _LOGGER.debug("Requesting Solarman access token...")
        async with self.session.post(url, json=payload) as resp:
            res_data = await resp.json()
            if res_data.get("success"):
                self._token = res_data.get("access_token")
                self._token_expires_at = now + 86400
                _LOGGER.debug("Solarman token acquired successfully.")
                return self._token
            else:
                _LOGGER.error("Failed to acquire Solarman token: %s", res_data)
                raise Exception(f"Auth error: {res_data.get('msg')}")

    async def async_get_current_data(self):
        """Fetch live telemetry data."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "deviceSn": self.device_sn,
            "deviceId": int(self.device_id) if str(self.device_id).isdigit() else self.device_id,
        }

        async with self.session.post(URL_DEVICE, headers=headers, json=payload) as resp:
            res_data = await resp.json()
            if res_data.get("success"):
                return res_data
            else:
                _LOGGER.error("Error fetching telemetry: %s", res_data)
                return None

    async def async_get_device_data(self):
        """Alias method for coordinator compatibility."""
        return await self.async_get_current_data()

    async def async_send_command(self, code: str, operation_type: int = 5, input_param: dict = None, timeout: int = 180):
        """Send command order to device via extendWeb payload."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "deviceSn": self.device_sn,
            "deviceId": int(self.device_id) if str(self.device_id).isdigit() else self.device_id,
            "cmdCode": code,
            "operationType": operation_type,
            "extendWeb": {
                "inputParam": input_param or {}
            }
        }

        _LOGGER.info("Sending command %s to Solarman API...", code)
        async with self.session.post(URL_COMMAND, headers=headers, json=payload) as resp:
            res_data = await resp.json()
            if not res_data.get("success"):
                _LOGGER.error("Failed to issue command %s: %s", code, res_data)
                raise Exception(f"Command error: {res_data.get('msg')}")

            order_id = res_data.get("orderId")
            if not order_id:
                return res_data

            _LOGGER.info("Command accepted. Order ID: %s. Polling result...", order_id)
            return await self._async_poll_order_status(token, order_id, timeout)

    async def _async_poll_order_status(self, token: str, order_id: str, timeout: int):
        """Poll order ID until status indicates completion."""
        url = "https://globalapi.solarmanpv.com/device/v1.0/command/status"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"orderId": order_id}

        start_time = time.time()
        while time.time() - start_time < timeout:
            async with self.session.post(url, headers=headers, json=payload) as resp:
                res = await resp.json()
                status = res.get("status")
                if status == "SUCCESS":
                    _LOGGER.info("Order %s executed successfully.", order_id)
                    return res
                elif status in ("FAILED", "TIMEOUT"):
                    _LOGGER.error("Order %s failed with status: %s", order_id, status)
                    raise Exception(f"Order failed with status {status}")
            await asyncio.sleep(5)

        raise Exception(f"Order polling timed out after {timeout} seconds.")
