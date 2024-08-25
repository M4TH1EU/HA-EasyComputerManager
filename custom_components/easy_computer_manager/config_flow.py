"""Config flow for Easy Computer Manager integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from paramiko.ssh_exception import AuthenticationException

from .computer import Computer
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("name"): str,
        vol.Required("host"): str,
        vol.Required("mac"): str,
        vol.Required("dualboot"): bool,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("port", default=22): int,
    }
)


class Hub:
    """Dummy for test connection"""

    def __init__(self, hass: HomeAssistant, host: str, username: str, password: str, port: int) -> None:
        """Init dummy hub."""
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._hass = hass
        self._name = host
        self._id = host.lower()

        self.computer = Computer(host, "", username, password, port)

    @property
    def hub_id(self) -> str:
        """ID for dummy."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connectivity to the computer is OK."""
        try:
            # TODO: check if reachable
            _LOGGER.info("Testing connection to %s", self._host)
            return True

        except AuthenticationException:
            return False


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data["host"]) < 3:
        raise InvalidHost

    hub = Hub(hass, data["host"], data["username"], data["password"], data["port"])

    _LOGGER.info("Validating configuration")
    if not await hub.test_connection():
        raise CannotConnect

    return {"title": data["host"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow"""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except (AuthenticationException, CannotConnect, InvalidHost) as ex:
                errors["base"] = str(ex)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
