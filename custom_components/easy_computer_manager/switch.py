# Some snippets of code are from the official wake_on_lan integration (inspiration for this custom component)

from __future__ import annotations

import asyncio
import logging
import subprocess as sp
from typing import Any

import voluptuous as vol
import wakeonlan
from homeassistant.components.switch import (SwitchEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME, )
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from paramiko.ssh_exception import AuthenticationException

from . import utils
from .const import SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, SERVICE_PUT_COMPUTER_TO_SLEEP, \
    SERVICE_START_COMPUTER_TO_WINDOWS, SERVICE_RESTART_COMPUTER, SERVICE_RESTART_TO_LINUX_FROM_WINDOWS, \
    SERVICE_CHANGE_MONITORS_CONFIG, SERVICE_STEAM_BIG_PICTURE, SERVICE_CHANGE_AUDIO_CONFIG, SERVICE_DEBUG_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    # Setup the computer switch
    mac_address: str = config.data.get(CONF_MAC)
    broadcast_address: str | None = config.data.get(CONF_BROADCAST_ADDRESS)
    broadcast_port: int | None = config.data.get(CONF_BROADCAST_PORT)
    host: str = config.data.get(CONF_HOST)
    name: str = config.data.get(CONF_NAME)
    dualboot: bool = config.data.get("dualboot")
    username: str = config.data.get(CONF_USERNAME)
    password: str = config.data.get(CONF_PASSWORD)
    port: int | None = config.data.get(CONF_PORT)

    # Register the computer switch
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

    # Synthax : (service_name: str, schema: dict, supports_response: SupportsResponse)
    services = [
        (SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, {}, SupportsResponse.NONE),
        (SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, {}, SupportsResponse.NONE),
        (SERVICE_RESTART_TO_LINUX_FROM_WINDOWS, {}, SupportsResponse.NONE),
        (SERVICE_PUT_COMPUTER_TO_SLEEP, {}, SupportsResponse.NONE),
        (SERVICE_START_COMPUTER_TO_WINDOWS, {}, SupportsResponse.NONE),
        (SERVICE_RESTART_COMPUTER, {}, SupportsResponse.NONE),
        (SERVICE_CHANGE_MONITORS_CONFIG, {vol.Required("monitors_config"): dict}, SupportsResponse.NONE),
        (SERVICE_STEAM_BIG_PICTURE, {vol.Required("action"): str}, SupportsResponse.NONE),
        (SERVICE_CHANGE_AUDIO_CONFIG, {
            vol.Optional("volume"): int,
            vol.Optional("mute"): bool,
            vol.Optional("input_device"): str,
            vol.Optional("output_device"): str
        }, SupportsResponse.NONE),
        (SERVICE_DEBUG_INFO, {}, SupportsResponse.ONLY),
    ]

    # Register the services
    for service in services:
        platform.async_register_entity_service(
            service[0],
            make_entity_service_schema(service[1]),
            service[0],
            supports_response=service[2]
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
    def device_info(self) -> DeviceInfo | None:
        """Return the device information."""
        if self._host is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=self._attr_name,
            manufacturer="Generic",
            model="Computer",
            sw_version=utils.get_operating_system_version(self._connection),
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
        )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:monitor" if self._state else "mdi:monitor-off"

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

        _LOGGER.debug(
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
            _LOGGER.error(
                "The computer with the IP address %s is not running a dualboot system or hasn't been configured "
                "correctly in the UI.",
                self._host)

    def restart_to_linux_from_windows(self) -> None:
        """Restart the computer to Linux from a running Windows by setting grub-reboot and restarting."""

        if self._dualboot:
            # TODO: check for default grub entry and adapt accordingly
            utils.restart_system(self._connection)
        else:
            _LOGGER.error(
                "The computer with the IP address %s is not running a dualboot system or hasn't been configured "
                "correctly in the UI.",
                self._host)

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
            _LOGGER.error(
                "The computer with the IP address %s is not running a dualboot system or hasn't been configured "
                "correctly in the UI.",
                self._host)

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

    def change_monitors_config(self, monitors_config: dict | None = None) -> None:
        """Change the monitors configuration using a YAML config file."""
        if monitors_config is not None and len(monitors_config) > 0:
            utils.change_monitors_config(self._connection, monitors_config)
        else:
            raise HomeAssistantError("The 'monitors_config' parameter must be a non-empty dictionary.")

    def steam_big_picture(self, action: str) -> None:
        """Controls Steam Big Picture mode."""

        if action is not None:
            utils.steam_big_picture(self._connection, action)
        else:
            raise HomeAssistantError("The 'action' parameter must be specified.")

    def change_audio_config(self, volume: int | None = None, mute: bool | None = None, input_device: str | None = None,
                            output_device: str | None = None) -> None:
        """Change the audio configuration using a YAML config file."""
        utils.change_audio_config(self._connection, volume, mute, input_device, output_device)

    def update(self) -> None:
        """Ping the computer to see if it is online and update the state."""
        timeout = 1
        ping_cmd = ["ping", "-c", "1", "-W", str(timeout), str(self._host)]
        status = sp.call(ping_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        self._state = not bool(status)

        # Update the state attributes and the connection only if the computer is on
        if self._state:
            if self._connection is None or not utils.test_connection(self._connection):
                self.renew_ssh_connection()

                if not self._state:
                    return

            self._attr_extra_state_attributes = {
                "operating_system": utils.get_operating_system(self._connection),
                "operating_system_version": utils.get_operating_system_version(self._connection),
                "mac_address": self._mac_address,
                "ip_address": self._host,
            }

    def renew_ssh_connection(self) -> None:
        """Renew the SSH connection."""
        _LOGGER.info("Renewing SSH connection to %s using username %s", self._host, self._username)

        if self._connection is not None:
            self._connection.close()

        try:
            self._connection = utils.create_ssh_connection(self._host, self._username, self._password)
            self._connection.open()
        except AuthenticationException as error:
            _LOGGER.error("Could not authenticate to %s using username %s: %s", self._host, self._username, error)
            self._state = False
        except Exception as error:
            _LOGGER.error("Could not connect to %s using username %s: %s", self._host, self._username, error)

            # Check if the error is due to timeout
            if "timed out" in str(error):
                _LOGGER.warning(
                    "Computer at %s does not respond to the SSH request. Possible causes: might be offline, "
                    "the firewall is blocking the SSH port, or the SSH server is offline and/or misconfigured.",
                    self._host
                )

            self._state = False

    def debug_info(self) -> ServiceResponse:
        """Prints debug info."""
        return utils.get_debug_info(self._connection)
