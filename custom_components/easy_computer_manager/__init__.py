"""The Easy Dualboot Computer Manager integration."""

# Some snippets of code are from the official wake_on_lan integration (inspiration for this custom component)

from __future__ import annotations

import logging
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import wakeonlan
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, SERVICE_SEND_MAGIC_PACKET, SERVICE_CHANGE_MONITORS_CONFIG

LOGGER = logging.getLogger(__name__)

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
    vol.Optional(CONF_BROADCAST_PORT): cv.port,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Easy Dualboot Computer Manager integration."""

    async def send_magic_packet(call: ServiceCall) -> None:
        """Send a magic packet to wake up a device."""
        mac_address = call.data.get(CONF_MAC)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        broadcast_port = call.data.get(CONF_BROADCAST_PORT)

        service_kwargs = {}
        if broadcast_address is not None:
            service_kwargs["ip_address"] = broadcast_address
        if broadcast_port is not None:
            service_kwargs["port"] = broadcast_port

        LOGGER.info(
            "Sending magic packet to MAC %s (broadcast: %s, port: %s)",
            mac_address,
            broadcast_address,
            broadcast_port,
        )

        await hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, mac_address, **service_kwargs)
        )

    # Register the wake on lan service
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Easy Dualboot Computer Manager integration."""
    return await hass.config_entries.async_forward_entry_unload(
        entry, "switch"
    )
