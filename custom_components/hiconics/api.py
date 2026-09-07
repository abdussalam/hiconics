"""Solarman API Client for Hiconics Integration."""

import asyncio
import json
import logging
import time
import aiohttp

from .const import (
    URL_TOKEN,
    URL_DEVICE_DATA,
    URL_COMMAND_SEND,
    URL_ORDER_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class SolarmanAPIClient:
    """Client for interacting with the Solarman Cloud API."""

    def __init__(self, session: aiohttp.ClientSession, config: dict):
        self.session = session
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.username = config.get("username")
        self.password = config.get("password")
        self.device_sn = config.get("device_sn")
        self.device_id = config.get("device_id")
        self.product = config.get("product", "0_1067_1")
        self.code_group = config.get("code_group", "G1200")
        
        self.token = None
        self.token_expires_at = 0  # Timestamp when token expires

    async def async_get_token(self) -> str:
        """Authenticate and store access token with expiration tracking."""
        url = f"{URL_TOKEN}?appId={self.app_id}&language=en"
        payload = {
            "appSecret": self.app_secret,
            "username": self.username,
            "password": self.password,
        }
        headers = {"Content-Type": "application/json"}

        _LOGGER.info("Requesting new access token from Solarman API...")
        async with self.session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("success") in (1, "1") or data.get("access_token"):
                self.token = data.get("access_token")
                
                # Solarman tokens default to 24 hours (86400s). Renew 5 mins early.
                expires_in = int(data.get("expires_in", 86400))
                self.token_expires_at = time.time() + max(expires_in - 300, 3600)
                
                _LOGGER.info(
                    "Successfully obtained new Solarman access token (valid for ~%s hours).",
                    round(expires_in / 3600, 1),
                )
                return self.token
            
            _LOGGER.error("Failed to authenticate with Solarman API: %s", data)
            raise Exception(f"Failed to authenticate with Solarman API: {data}")

    async def _headers(self) -> dict:
        """Get request headers, renewing token only if missing or expired."""
        if not self.token or time.time() >= self.token_expires_at:
            _LOGGER.info("Cached token is missing or expired. Fetching fresh token...")
            await self.async_get_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _is_token_error(self, resp_status: int, data: dict) -> bool:
        """Detect if API response indicates an invalid or expired token."""
        if resp_status == 401:
            return True
        if isinstance(data, dict):
            code = str(data.get("code", ""))
            msg = str(data.get("msg", "")).lower()
            if code.startswith("2101") or "token" in msg or "unauthorized" in msg:
                return True
        return False

    async def async_get_device_data(self) -> dict:
        """Fetch current inverter/battery device metrics."""
        url = f"{URL_DEVICE_DATA}?language=en"
        payload = {"deviceSn": self.device_sn}
        headers = await self._headers()

        async with self.session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            if self._is_token_error(resp.status, data):
                _LOGGER.warning("Token rejected by API. Refreshing token and retrying...")
                self.token = None  # Invalidate token cache
                headers = await self._headers()
                async with self.session.post(url, json=payload, headers=headers) as resp_retry:
                    return await resp_retry.json()
            return data

    async def async_send_command(self, code: str, operation_type: int, input_param: dict, timeout: int = 180) -> dict:
        """Send a control command to the inverter and wait for task completion."""
        headers = await self._headers()
        payload = {
            "product": self.product,
            "deviceSn": self.device_sn,
            "deviceId": self.device_id,
            "code": code,
            "codeGroup": self.code_group,
            "operationType": operation_type,
            "extendWeb": json.dumps({"inputParam": input_param}),
            "orderTimeout": timeout,
        }

        _LOGGER.info("Sending Solarman command '%s' (Operation Type: %s)...", code, operation_type)

        async with self.session.post(URL_COMMAND_SEND, json=payload, headers=headers) as resp:
            data = await resp.json()
            if self._is_token_error(resp.status, data):
                _LOGGER.warning("Token rejected during command send. Refreshing token and retrying...")
                self.token = None  # Invalidate token cache
                headers = await self._headers()
                async with self.session.post(URL_COMMAND_SEND, json=payload, headers=headers) as resp_retry:
                    res = await resp_retry.json()
            else:
                res = data

            order_id = res.get("id")
            if order_id:
                _LOGGER.info("Order submitted (ID: %s). Polling status...", order_id)
                return await self.async_poll_order_status(order_id, is_read=(operation_type == 4))
            
            _LOGGER.error("Command send failed or did not return an Order ID. Response: %s", res)
            return res

    async def async_poll_order_status(self, order_id: str, is_read: bool = False, retries: int = 12, delay: int = 5) -> dict:
        """Poll order status until analysisResult is populated or task completes."""
        headers = await self._headers()
        url = f"{URL_ORDER_STATUS}/{order_id}"

        await asyncio.sleep(5)

        for attempt in range(1, retries + 1):
            async with self.session.get(url, headers=headers) as resp:
                data = await resp.json()

                if self._is_token_error(resp.status, data):
                    _LOGGER.warning("Token expired while polling order %s. Refreshing...", order_id)
                    self.token = None
                    headers = await self._headers()
                    continue

                if is_read:
                    if data.get("analysisResult"):
                        _LOGGER.info("Order %s returned analysisResult on attempt %s.", order_id, attempt)
                        return data
                else:
                    status = str(data.get("status", "")).upper()
                    exec_status = str(data.get("executeStatus", "")).upper()
                    if status in ("SUCCESS", "SUCCEEDED", "FINISHED") or exec_status in ("SUCCESS", "1"):
                        _LOGGER.info("Write Order %s completed on attempt %s.", order_id, attempt)
                        return data

                status = str(data.get("status", "")).upper()
                if status in ("FAILED", "ERROR"):
                    _LOGGER.error("Order %s failed on attempt %s: %s", order_id, attempt, data)
                    return data

            _LOGGER.info("Order %s processing (attempt %s/%s). Waiting %ss...", order_id, attempt, retries, delay)
            await asyncio.sleep(delay)

        _LOGGER.error("Order %s timed out after %s retries.", order_id, retries)
        return {"status": "TIMEOUT", "id": order_id}
