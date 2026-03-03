"""Config flow for BMW Connected Ride integration."""

import asyncio
import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import BMWAuthClient
from .const import CONF_REGION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): vol.In(
            {
                "ROW": "Rest of World",
                "NA": "North America",
            }
        ),
    }
)


class BMWConnectedRideConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BMW Connected Ride."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._region: str | None = None
        self._auth_client: BMWAuthClient | None = None
        self._login_task: asyncio.Task[Any] | None = None
        self._device_code: str | None = None
        self._user_code: str | None = None
        self._verification_uri: str | None = None
        self._interval: int = 5
        self._expires_in: int = 1800

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step — region selection."""
        _LOGGER.debug("Config flow step: user")

        if user_input is not None:
            self._region = user_input[CONF_REGION]
            _LOGGER.debug("Region selected: %s", self._region)
            return await self.async_step_device_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def async_step_device_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device code display and background polling."""
        _LOGGER.debug("Config flow step: device_auth")

        if self._auth_client is None:
            assert self._region is not None, "region must be set before device auth step"
            session = async_get_clientsession(self.hass)
            self._auth_client = BMWAuthClient(
                region=self._region,
                session=session,
            )
            _LOGGER.debug("Created BMWAuthClient for region %s", self._region)

            device_response = await self._auth_client.request_device_code()
            self._device_code = device_response["device_code"]
            self._user_code = device_response["user_code"]
            self._verification_uri = device_response["verification_uri"]
            self._interval = device_response.get("interval", 5)
            self._expires_in = device_response.get("expires_in", 1800)
            _LOGGER.debug(
                "Device code received, user_code=%s verification_uri=%s",
                self._user_code,
                self._verification_uri,
            )

        assert self._device_code is not None, "device_code must be set before polling"
        assert self._user_code is not None, "user_code must be set before showing form"
        assert self._verification_uri is not None, "verification_uri must be set before showing form"

        if self._login_task is None:
            self._login_task = self.hass.async_create_task(
                self._auth_client.poll_for_token(
                    self._device_code,
                    self._interval,
                    self._expires_in,
                )
            )
            _LOGGER.debug("Background polling task started")

        if self._login_task.done():
            exc = self._login_task.exception()
            if exc is not None:
                _LOGGER.warning("Device code auth failed: %s", exc)
                return self.async_show_progress_done(next_step_id="timeout")
            _LOGGER.debug("Device code auth succeeded, proceeding to finish")
            return self.async_show_progress_done(next_step_id="finish")

        return self.async_show_progress(
            step_id="device_auth",
            progress_action="wait_for_device",
            description_placeholders={
                "url": self._verification_uri,
                "code": self._user_code,
            },
            progress_task=self._login_task,
        )

    async def async_step_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication timeout or error — allow retry."""
        _LOGGER.debug("Config flow step: timeout")

        # Clean up old task to prevent leaks
        if self._login_task is not None:
            self._login_task.cancel()
            self._login_task = None

        # Reset auth client so a fresh device code is requested on retry
        self._auth_client = None

        if user_input is not None:
            return await self.async_step_device_auth()

        return self.async_show_form(
            step_id="timeout",
            errors={"base": "timeout"},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after successful authentication."""
        _LOGGER.debug("Config flow step: finish")

        assert self._auth_client is not None, "auth_client must be set before finish step"

        client_id_header = str(uuid.uuid4())

        data = {
            "region": self._region,
            "access_token": self._auth_client.access_token,
            "refresh_token": self._auth_client.refresh_token,
            "token_expiry": self._auth_client.token_expiry,
            "client_id_header": client_id_header,
        }

        await self.async_set_unique_id(self._region)
        self._abort_if_unique_id_configured()

        # Check if we're in a reauth context
        if self.source == "reauth":
            reauth_entry = self._get_reauth_entry()
            _LOGGER.debug("Reauth complete, updating config entry for region %s", self._region)
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={**reauth_entry.data, **data},
            )

        _LOGGER.debug("New config entry created for region %s", self._region)
        return self.async_create_entry(title="BMW Connected Ride", data=data)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow entry point — triggered when tokens become invalid."""
        _LOGGER.debug("Config flow step: reauth")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation — user acknowledges they need to re-authenticate."""
        _LOGGER.debug("Config flow step: reauth_confirm")

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            self._region = reauth_entry.data["region"]
            _LOGGER.debug("Reauth confirmed, region=%s", self._region)
            return await self.async_step_device_auth()

        return self.async_show_form(step_id="reauth_confirm")
