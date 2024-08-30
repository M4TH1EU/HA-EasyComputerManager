async def format_debug_information(computer: 'Computer'):  # importing Computer causes circular import (how to fix?)
    """Return debug information about the host system."""

    data = {
        'os': {
            'name': computer.operating_system,
            'version': computer.operating_system_version,
            'desktop_environment': computer.desktop_environment
        },
        'connection': {
            'host': computer.host,
            'mac': computer.mac,
            'username': computer.username,
            'port': computer.port,
            'dualboot': computer.dualboot,
            'is_on': await computer.is_on()
        },
        'grub': {
            'windows_entry': computer.windows_entry_grub
        },
        'audio': {
            'speakers': computer.audio_config.get('speakers'),
            'microphones': computer.audio_config.get('microphones')
        },
        'monitors': computer.monitors_config,
        'bluetooth_devices': computer.bluetooth_devices
    }

    return data


def get_bluetooth_devices_as_str(computer: 'Computer') -> str:
    """Return the bluetooth devices as a string."""
    devices = computer.bluetooth_devices

    if not devices:
        return ""

    return "; ".join([f"{device['name']} ({device['address']})" for device in devices])
