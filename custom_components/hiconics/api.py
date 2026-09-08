"""Solarman Cloud API client for Hiconics."""

import asyncio
import hashlib
import logging
import time
import json

from .const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_DEVICE_SN,
    CONF_DEVICE_ID,
    CONF_API_DOMAIN,
    CONF_PRODUCT_CODE,
    CONF_CODE_GROUP,
    DEFAULT_API_DOMAIN,
    DEFAULT_PRODUCT_CODE,
    DEFAULT_CODE_GROUP,
)

_LOGGER = logging.getLogger(__name__)

URL_TOKEN = "https://globalapi.solarmanpv.com/account/v1.0/token"
URL_DEVICE = "https://globalapi.solarmanpv.com/device/v1.0/currentData"

URL_COMMAND = "https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send"
URL_POLL = "https://globaldc-pro.solarmanpv.com/order-s/order/action/"


class SolarmanAPIClient:
    """API Client to interface with Solarman Cloud."""

    def __init__(self, session, config):
        self.session = session
        self.username = config.get(CONF_USERNAME, "")
        self.password_hash = hashlib.sha256(
            config.get(CONF_PASSWORD, "").encode("utf-8")
        ).hexdigest()
        self.app_id = config.get(CONF_APP_ID, "")
        self.app_secret = config.get(CONF_APP_SECRET, "")
        self.device_sn = config.get(CONF_DEVICE_SN, "")
        self.device_id = config.get(CONF_DEVICE_ID, "")
        
        # New configurable parameters
        self.api_domain = config.get(CONF_API_DOMAIN, DEFAULT_API_DOMAIN)
        self.product_code = config.get(CONF_PRODUCT_CODE, DEFAULT_PRODUCT_CODE)
        self.code_group = config.get(CONF_CODE_GROUP, DEFAULT_CODE_GROUP)

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
            "password": self.password_hash,
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
        """Send command order mirroring the Node-RED PRO flow."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Dynamically build the command URL based on user's region
        command_url = f"https://{self.api_domain}/order-s/order/action/control/send"

        extend_web_str = json.dumps({"inputParam": input_param or {}})

        payload = {
            "product": self.product_code,      # Dynamic product code
            "deviceSn": self.device_sn,
            "deviceId": str(self.device_id),
            "code": code,
            "codeGroup": self.code_group,      # Dynamic code group
            "operationType": operation_type,
            "extendWeb": extend_web_str,
            "orderTimeout": timeout
        }

        _LOGGER.info("Sending PRO command %s...", code)
        async with self.session.post(command_url, headers=headers, json=payload) as resp:
            res_data = await resp.json()
            
            order_id = res_data.get("id")
            if not order_id:
                _LOGGER.error("PRO API Command failed or no ID returned: %s", res_data)
                return res_data

            _LOGGER.info("Command accepted. Order ID: %s. Polling result...", order_id)
            return await self._async_poll_order_status(token, order_id, timeout)

    async def _async_poll_order_status(self, token: str, order_id: str, timeout: int):
        """Poll PRO order ID using a GET request."""
        # Dynamically build the poll URL
        poll_url = f"https://{self.api_domain}/order-s/order/action/{order_id}"
        headers = {"Authorization": f"Bearer {token}"}

        start_time = time.time()
        await asyncio.sleep(10)

        while time.time() - start_time < timeout:
            async with self.session.get(poll_url, headers=headers) as resp:
                res = await resp.json()
                
                if res.get("analysisResult"):
                    _LOGGER.info("Order %s executed successfully.", order_id)
                    return res
                elif str(res.get("success")) == "0":
                    _LOGGER.error("Order %s failed: %s", order_id, res)
                    raise Exception(f"Order failed: {res}")
                    
            await asyncio.sleep(5)

        raise Exception(f"Order polling timed out after {timeout} seconds.") 
