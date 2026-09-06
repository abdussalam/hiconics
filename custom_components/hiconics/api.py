"""Solarman API Client for Hiconics Integration."""

import asyncio
import json
import logging
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

    async def async_get_token(self) -> str:
        """Authenticate and store access token."""
        url = f"{URL_TOKEN}?appId={self.app_id}&language=en"
        payload = {
            "appSecret": self.app_secret,
            "username": self.username,
            "password": self.password,
        }
        headers = {"Content-Type": "application/json"}

        async with self.session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("success") in (1, "1") or data.get("access_token"):
                self.token = data.get("access_token")
                return self.token
            raise Exception(f"Failed to authenticate with Solarman API: {data}")

    async def _headers(self) -> dict:
        if not self.token:
            await self.async_get_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    async def async_get_device_data(self) -> dict:
        """Fetch current inverter/battery device metrics."""
        url = f"{URL_DEVICE_DATA}?language=en"
        payload = {"deviceSn": self.device_sn}
        headers = await self._headers()

        async with self.session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 401:
                await self.async_get_token()
                headers = await self._headers()
                async with self.session.post(url, json=payload, headers=headers) as resp_retry:
                    return await resp_retry.json()
            return await resp.json()

    async def async_send_command(self, code: str, operation_type: int, input_param: dict, timeout: int = 180) -> dict:
        """Send a control command to the inverter (Operation Type 4 or 5)."""
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

        async with self.session.post(URL_COMMAND_SEND, json=payload, headers=headers) as resp:
            res = await resp.json()
            order_id = res.get("id")
            if order_id:
                return await self.async_poll_order_status(order_id)
            return res

    async def async_poll_order_status(self, order_id: str, retries: int = 6, delay: int = 5) -> dict:
        """Poll task status until completion."""
        headers = await self._headers()
        url = f"{URL_ORDER_STATUS}/{order_id}"

        for _ in range(retries):
            await asyncio.sleep(delay)
            async with self.session.get(url, headers=headers) as resp:
                data = await resp.json()
                if data.get("status") in ("SUCCESS", "FAILED"):
                    return data
        return {"status": "TIMEOUT", "id": order_id}
