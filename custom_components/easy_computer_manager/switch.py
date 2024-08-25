# Some snippets of code are from the official wake_on_lan integration (inspiration for this custom component)

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import (SwitchEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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

from . import utils, computer_utils
from .computer import Computer, OSType
from .const import SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, SERVICE_PUT_COMPUTER_TO_SLEEP, \
    SERVICE_START_COMPUTER_TO_WINDOWS, SERVICE_RESTART_COMPUTER, SERVICE_RESTART_TO_LINUX_FROM_WINDOWS, \
    SERVICE_CHANGE_MONITORS_CONFIG, SERVICE_STEAM_BIG_PICTURE, SERVICE_CHANGE_AUDIO_CONFIG, SERVICE_DEBUG_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    # Retrieve the data from the config flow
    mac_address: str = config.data.get(CONF_MAC)
    # broadcast_address: str | None = config.data.get(CONF_BROADCAST_ADDRESS)
    # broadcast_port: int | None = config.data.get(CONF_BROADCAST_PORT)
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

    # Register the services that depends on the switch
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
            dualboot: bool | False,
            username: str,
            password: str,
            port: int | None,
    ) -> None:
        """Initialize the WOL switch."""

        self._hass = hass
        self._attr_name = name

        self.computer = Computer(host, mac_address, username, password, port, dualboot)

        self._state = False
        self._attr_assumed_state = host is None
        self._attr_should_poll = bool(not self._attr_assumed_state)
        self._attr_unique_id = dr.format_mac(mac_address)
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device information."""
        # TODO: remove this?
        # if self._host is None:
        #     return None

        return DeviceInfo(
            identifiers={(DOMAIN, self.computer.mac)},
            name=self._attr_name,
            manufacturer="Generic",
            model="Computer",
            sw_version=self.computer.get_operating_system_version(),
            connections={(dr.CONNECTION_NETWORK_MAC, self.computer.mac)},
        )

    @property
    def icon(self) -> str:
        return "mdi:monitor" if self._state else "mdi:monitor-off"

    @property
    def is_on(self) -> bool:
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        self.computer.start()

        if self._attr_assumed_state:
            self._state = True
            self.async_write_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        self.computer.shutdown()

        if self._attr_assumed_state:
            self._state = False
            self.async_write_ha_state()

    # Services
    def restart_to_windows_from_linux(self) -> None:
        """Restart the computer to Windows from a running Linux by setting grub-reboot and restarting."""
        self.computer.restart(OSType.LINUX, OSType.WINDOWS)

    def restart_to_linux_from_windows(self) -> None:
        """Restart the computer to Linux from a running Windows by setting grub-reboot and restarting."""
        self.computer.restart()

    def put_computer_to_sleep(self) -> None:
        self.computer.setup()

    def start_computer_to_windows(self) -> None:
        async def wait_task():
            while not self.is_on:
                pass
                # await asyncio.sleep(3)

            self.computer.restart(OSType.LINUX, OSType.WINDOWS)

        """Start the computer to Linux, wait for it to boot, and then set grub-reboot and restart."""
        self.computer.start()
        self._hass.loop.create_task(wait_task())

    def restart_computer(self) -> None:
        self.computer.restart()

    def change_monitors_config(self, monitors_config: dict | None = None) -> None:
        """Change the monitors configuration using a YAML config file."""
        self.computer.change_monitors_config(monitors_config)

    def steam_big_picture(self, action: str) -> None:
        match action:
            case "start":
                self.computer.start_steam_big_picture()
            case "stop":
                self.computer.stop_steam_big_picture()
            case "exit":
                self.computer.exit_steam_big_picture()


    def change_audio_config(self, volume: int | None = None, mute: bool | None = None, input_device: str | None = None,
                            output_device: str | None = None) -> None:
        """Change the audio configuration using a YAML config file."""
        self.computer.change_audio_config(volume, mute, input_device, output_device)

    def debug_info(self) -> ServiceResponse:
        """Prints debug info."""
        return computer_utils.get_debug_info(self.computer)


    def update(self) -> None:
        """Ping the computer to see if it is online and update the state."""
        self._state = self.computer.is_on()

        # Update the state attributes and the connection only if the computer is on
        if self._state:
            self._attr_extra_state_attributes = {
                "operating_system": self.computer.get_operating_system(),
                "operating_system_version": self.computer.get_operating_system_version(),
                "mac_address": self.computer.mac,
                "ip_address": self.computer.host,
                "connected_devices": self.computer.get_bluetooth_devices(as_str=True),
            }

