from __future__ import annotations

import asyncio
from typing import Any, Dict

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import entity_platform, device_registry as dr
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .computer import OSType, Computer
from .computer.utils import format_debug_information, get_bluetooth_devices_as_str
from .const import (
    DOMAIN, SERVICE_RESTART_TO_WINDOWS_FROM_LINUX, SERVICE_PUT_COMPUTER_TO_SLEEP,
    SERVICE_START_COMPUTER_TO_WINDOWS, SERVICE_RESTART_COMPUTER,
    SERVICE_RESTART_TO_LINUX_FROM_WINDOWS, SERVICE_CHANGE_MONITORS_CONFIG,
    SERVICE_STEAM_BIG_PICTURE, SERVICE_CHANGE_AUDIO_CONFIG, SERVICE_DEBUG_INFO
)


async def async_setup_entry(
        hass: HomeAssistant,
        config: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the computer switch from a config entry."""
    mac_address = config.data[CONF_MAC]
    host = config.data[CONF_HOST]
    name = config.data[CONF_NAME]
    dualboot = config.data.get("dualboot", False)
    username = config.data[CONF_USERNAME]
    password = config.data[CONF_PASSWORD]
    port = config.data.get(CONF_PORT)

    async_add_entities(
        [ComputerSwitch(hass, name, host, mac_address, dualboot, username, password, port)],
        True
    )

    platform = entity_platform.async_get_current_platform()

    # Service registrations
    services = [
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

    # Register services with their schemas
    for service_name, schema, supports_response in services:
        platform.async_register_entity_service(
            service_name,
            make_entity_service_schema(schema),
            service_name,
            supports_response=supports_response
        )


class ComputerSwitch(SwitchEntity):
    """Representation of a computer switch entity."""

    def __init__(
            self,
            hass: HomeAssistant,
            name: str,
            host: str | None,
            mac_address: str,
            dualboot: bool,
            username: str,
            password: str,
            port: int | None,
    ) -> None:
        """Initialize the computer switch entity."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = dr.format_mac(mac_address)
        self._state = False
        self._attr_should_poll = not self._attr_assumed_state
        self._attr_extra_state_attributes = {}

        self.computer = Computer(host, mac_address, username, password, port, dualboot)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.computer.mac)},
            name=self._attr_name,
            manufacturer="Generic",
            model="Computer",
            sw_version=self.computer.operating_system_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.computer.mac)},
        )

    @property
    def icon(self) -> str:
        return "mdi:monitor" if self._state else "mdi:monitor-off"

    @property
    def is_on(self) -> bool:
        """Return true if the computer is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the computer on using Wake-on-LAN."""
        await self.computer.start()

        if self._attr_assumed_state:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the computer off via shutdown command."""
        await self.computer.shutdown()

        if self._attr_assumed_state:
            self._state = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the state by checking if the computer is on."""
        is_on = await self.computer.is_on()
        if self.is_on != is_on:
            self._state = is_on
            # self.async_write_ha_state()

        # If the computer is on, update its attributes
        if is_on:
            await self.computer.update(is_on)

            self._attr_extra_state_attributes = {
                "operating_system": self.computer.operating_system,
                "operating_system_version": self.computer.operating_system_version,
                "mac_address": self.computer.mac,
                "ip_address": self.computer.host,
                "connected_devices": get_bluetooth_devices_as_str(self.computer),
            }

    # Service methods for various functionalities
    async def restart_to_windows_from_linux(self) -> None:
        """Restart the computer from Linux to Windows."""
        await self.computer.restart(OSType.LINUX, OSType.WINDOWS)

    async def restart_to_linux_from_windows(self) -> None:
        """Restart the computer from Windows to Linux."""
        await self.computer.restart(OSType.WINDOWS, OSType.LINUX)

    async def put_computer_to_sleep(self) -> None:
        """Put the computer to sleep."""
        await self.computer.put_to_sleep()

    async def start_computer_to_windows(self) -> None:
        """Start the computer to Windows after booting into Linux first."""
        await self.computer.start()

        async def wait_and_reboot() -> None:
            """Wait until the computer is on, then restart to Windows."""
            while not await self.computer.is_on():
                await asyncio.sleep(3)
            await self.computer.restart(OSType.LINUX, OSType.WINDOWS)

        self.hass.loop.create_task(wait_and_reboot())

    async def restart_computer(self) -> None:
        """Restart the computer."""
        await self.computer.restart()

    async def change_monitors_config(self, monitors_config: Dict[str, Any]) -> None:
        """Change the monitor configuration."""
        await self.computer.set_monitors_config(monitors_config)

    async def steam_big_picture(self, action: str) -> None:
        """Control Steam Big Picture mode."""
        await self.computer.steam_big_picture(action)

    async def change_audio_config(
            self, volume: int | None = None, mute: bool | None = None,
            input_device: str | None = None, output_device: str | None = None
    ) -> None:
        """Change the audio configuration."""
        await self.computer.set_audio_config(volume, mute, input_device, output_device)

    async def debug_info(self) -> ServiceResponse:
        """Return debug information."""
        return await format_debug_information(self.computer)
