# Some code is from the official wake_on_lan integration

from __future__ import annotations

import asyncio
import logging
import subprocess as sp
from typing import Any

import voluptuous as vol
import wakeonlan
from homeassistant.components.switch import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from paramiko.ssh_exception import AuthenticationException

from . import utils
from .const import SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, SERVICE_PUT_COMPUTER_TO_SLEEP, \
    SERVICE_START_COMPUTER_TO_WINDOWS, RESTART_COMPUTER

_LOGGER = logging.getLogger(__name__)

CONF_OFF_ACTION = "turn_off"

DEFAULT_NAME = "Computer Management (WoL, SoL)"
DEFAULT_PING_TIMEOUT = 1

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
        vol.Required(CONF_HOST): cv.string,
        vol.Required("dualboot", default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME, default="root"): cv.string,
        vol.Required(CONF_PASSWORD, default="root"): cv.string,
        vol.Optional(CONF_PORT, default=22): cv.string,
    }
)


async def async_setup_entry(
        hass: HomeAssistant,
        config: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    mac_address: str = config.data.get(CONF_MAC)
    broadcast_address: str | None = config.data.get(CONF_BROADCAST_ADDRESS)
    broadcast_port: int | None = config.data.get(CONF_BROADCAST_PORT)
    host: str = config.data.get(CONF_HOST)
    name: str = config.data.get(CONF_NAME)
    dualboot: bool = config.data.get("dualboot")
    username: str = config.data.get(CONF_USERNAME)
    password: str = config.data.get(CONF_PASSWORD)
    port: int | None = config.data.get(CONF_PORT)

    async_add_entities(
        [
            ComputerSwitch(
                hass,
                name,
                host,
                mac_address,
                broadcast_address,
                broadcast_port,
                dualboot,
                username,
                password,
                port,
            ),
        ],
        host is not None,
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESTART_TO_WINDOWS_FROM_LINUX,
        {},
        SERVICE_RESTART_TO_WINDOWS_FROM_LINUX,
    )
    platform.async_register_entity_service(
        SERVICE_PUT_COMPUTER_TO_SLEEP,
        {},
        SERVICE_PUT_COMPUTER_TO_SLEEP,
    )
    platform.async_register_entity_service(
        SERVICE_START_COMPUTER_TO_WINDOWS,
        {},
        SERVICE_START_COMPUTER_TO_WINDOWS,
    )
    platform.async_register_entity_service(
        RESTART_COMPUTER,
        {},
        RESTART_COMPUTER,
    )


class ComputerSwitch(SwitchEntity):
    """Representation of a computer switch."""

    def __init__(
            self,
            hass: HomeAssistant,
            name: str,
            host: str | None,
            mac_address: str,
            broadcast_address: str | None,
            broadcast_port: int | None,
            dualboot: bool | False,
            username: str,
            password: str,
            port: int | None,
    ) -> None:
        """Initialize the WOL switch."""

        self._hass = hass
        self._attr_name = name
        self._host = host
        self._mac_address = mac_address
        self._broadcast_address = broadcast_address
        self._broadcast_port = broadcast_port
        self._dualboot = dualboot
        self._username = username
        self._password = password
        self._port = port
        self._state = False
        self._attr_assumed_state = host is None
        self._attr_should_poll = bool(not self._attr_assumed_state)
        self._attr_unique_id = dr.format_mac(mac_address)
        self._attr_extra_state_attributes = {}
        self._connection = utils.create_ssh_connection(self._host, self._username, self._password)

    @property
    def is_on(self) -> bool:
        """Return true if the computer switch is on."""
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the computer on using wake on lan."""
        service_kwargs: dict[str, Any] = {}
        if self._broadcast_address is not None:
            service_kwargs["ip_address"] = self._broadcast_address
        if self._broadcast_port is not None:
            service_kwargs["port"] = self._broadcast_port

        _LOGGER.info(
            "Send magic packet to mac %s (broadcast: %s, port: %s)",
            self._mac_address,
            self._broadcast_address,
            self._broadcast_port,
        )

        wakeonlan.send_magic_packet(self._mac_address, **service_kwargs)

        if self._attr_assumed_state:
            self._state = True
            self.async_write_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the computer off using appropriate shutdown command based on running OS and/or distro."""
        utils.shutdown_system(self._connection)

        if self._attr_assumed_state:
            self._state = False
            self.async_write_ha_state()

    def restart_to_windows_from_linux(self) -> None:
        """Restart the computer to Windows from a running Linux by setting grub-reboot and restarting."""

        if self._dualboot:
            utils.restart_to_windows_from_linux(self._connection)
        else:
            _LOGGER.error("This computer is not running a dualboot system.")

    def put_computer_to_sleep(self) -> None:
        """Put the computer to sleep using appropriate sleep command based on running OS and/or distro."""
        utils.sleep_system(self._connection)

    def start_computer_to_windows(self) -> None:
        """Start the computer to Linux, wait for it to boot, and then set grub-reboot and restart."""
        self.turn_on()

        if self._dualboot:
            # Wait for the computer to boot using a dedicated thread to avoid blocking the main thread
            self._hass.loop.create_task(self.service_restart_to_windows_from_linux())

        else:
            _LOGGER.error("This computer is not running a dualboot system.")

    async def service_restart_to_windows_from_linux(self) -> None:
        """Method to be run in a separate thread to wait for the computer to boot and then reboot to Windows."""
        while not self.is_on:
            await asyncio.sleep(3)

        await utils.restart_to_windows_from_linux(self._connection)

    def restart_computer(self) -> None:
        """Restart the computer using appropriate restart command based on running OS and/or distro."""

        # TODO: check for default grub entry and adapt accordingly
        if self._dualboot and not utils.is_unix_system(connection=self._connection):
            utils.restart_system(self._connection)

            # Wait for the computer to boot using a dedicated thread to avoid blocking the main thread
            self.restart_to_windows_from_linux()
        else:
            utils.restart_system(self._connection)

    def update(self) -> None:
        """Ping the computer to see if it is online and update the state."""
        ping_cmd = [
            "ping",
            "-c",
            "1",
            "-W",
            str(DEFAULT_PING_TIMEOUT),
            str(self._host),
        ]
        status = sp.call(ping_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        self._state = not bool(status)

        # Update the state attributes and the connection only if the computer is on
        if self._state:
            if not utils.test_connection(self._connection):
                _LOGGER.info("RENEWING SSH CONNECTION")

                if self._connection is not None:
                    self._connection.close()

                self._connection = utils.create_ssh_connection(self._host, self._username, self._password)

                try:
                    self._connection.open()
                except AuthenticationException as error:
                    _LOGGER.error("Could not authenticate to %s: %s", self._host, error)
                    self._state = False
                    return
                except Exception as error:
                    _LOGGER.error("Could not connect to %s: %s", self._host, error)
                    self._state = False
                    return

            self._attr_extra_state_attributes = {
                "operating_system": utils.get_operating_system(self._connection),
                "operating_system_version": utils.get_operating_system_version(
                    self._connection
                ),
                "mac_address": self._mac_address,
                "ip_address": self._host,
            }
