import re

from custom_components.easy_computer_manager import LOGGER
from custom_components.easy_computer_manager.computer.common import CommandOutput


async def format_debug_information(computer: 'Computer'):  # importing Computer causes circular import (how to fix?)
    """Return debug information about the host system."""

    data = {
        'os': {
            'name': computer.operating_system,
            'version': computer.operating_system_version,
            'desktop_environment': computer.desktop_environment
        },
        'connection':{
            'host': computer.host,
            'mac': computer.mac,
            'username': computer.username,
            'port': computer.port,
            'dualboot': computer.dualboot,
            'is_on': await computer.is_on()
        },
        'grub':{
            'windows_entry': computer.windows_entry_grub
        },
        'audio':{
            'speakers': computer.audio_config.get('speakers'),
            'microphones': computer.audio_config.get('microphones')
        },
        'monitors': computer.monitors_config,
        'bluetooth_devices': computer.bluetooth_devices
    }

    return data


def parse_gnome_monitors_output(config: str) -> list:
    """
    Parse the GNOME monitors configuration.

    :param config:
        The output of the gnome-monitor-config list command.

    :type config: str

    :returns: list
        The parsed monitors configuration.
    """

    monitors = []
    current_monitor = None

    for line in config.split('\n'):
        monitor_match = re.match(r'^Monitor \[ (.+?) \] (ON|OFF)$', line)
        if monitor_match:
            if current_monitor:
                monitors.append(current_monitor)
            source, status = monitor_match.groups()
            current_monitor = {'source': source, 'status': status, 'names': [], 'resolutions': []}
        elif current_monitor:
            display_name_match = re.match(r'^\s+display-name: (.+)$', line)
            resolution_match = re.match(r'^\s+(\d+x\d+@\d+(?:\.\d+)?).*$', line)
            if display_name_match:
                current_monitor['names'].append(display_name_match.group(1).replace('"', ''))
            elif resolution_match:
                # Don't include resolutions under 1280x720
                if int(resolution_match.group(1).split('@')[0].split('x')[0]) >= 1280:

                    # If there are already resolutions in the list, check if the framerate between the last is >1
                    if len(current_monitor['resolutions']) > 0:
                        last_resolution = current_monitor['resolutions'][-1]
                        last_resolution_size = last_resolution.split('@')[0]
                        this_resolution_size = resolution_match.group(1).split('@')[0]

                        # Only truncate some framerates if the resolution are the same
                        if last_resolution_size == this_resolution_size:
                            last_resolution_framerate = float(last_resolution.split('@')[1])
                            this_resolution_framerate = float(resolution_match.group(1).split('@')[1])

                            # If the difference between the last resolution framerate and this one is >1, ignore it
                            if last_resolution_framerate - 1 > this_resolution_framerate:
                                current_monitor['resolutions'].append(resolution_match.group(1))
                        else:
                            # If the resolution is different, this adds the new resolution
                            # to the list without truncating
                            current_monitor['resolutions'].append(resolution_match.group(1))
                    else:
                        # This is the first resolution, add it to the list
                        current_monitor['resolutions'].append(resolution_match.group(1))

    if current_monitor:
        monitors.append(current_monitor)

    return monitors


def parse_pactl_output(config_speakers: str, config_microphones: str) -> dict[str, list]:
    """
    Parse the pactl audio configuration.

    :param config_speakers:
        The output of the pactl list sinks command.
    :param config_microphones:
        The output of the pactl list sources command.

    :type config_speakers: str
    :type config_microphones: str

    :returns: dict
        The parsed audio configuration.

    """

    config = {'speakers': [], 'microphones': []}

    def parse_device_info(lines, device_type):
        devices = []
        current_device = {}

        for line in lines:
            if line.startswith(f"{device_type} #"):
                if current_device and "Monitor" not in current_device['description']:
                    devices.append(current_device)
                current_device = {'id': int(re.search(r'#(\d+)', line).group(1))}
            elif line.startswith("	Name:"):
                current_device['name'] = line.split(":")[1].strip()
            elif line.startswith("	State:"):
                current_device['state'] = line.split(":")[1].strip()
            elif line.startswith("	Description:"):
                current_device['description'] = line.split(":")[1].strip()

        if current_device:
            devices.append(current_device)

        return devices

    config['speakers'] = parse_device_info(config_speakers.split('\n'), 'Sink')
    config['microphones'] = parse_device_info(config_microphones.split('\n'), 'Source')

    return config


def parse_bluetoothctl(command: CommandOutput, connected_devices_only: bool = True,
                       return_as_string: bool = False) -> list | str:
    """Parse the bluetoothctl info command.

    :param command:
        The command output.
    :param connected_devices_only:
        Only return connected devices.
        Will return all devices, connected or not, if False.

    :type command: :class: CommandOutput
    :type connected_devices_only: bool

    :returns: str | list
        The parsed bluetooth devices.

    """

    if not command.successful():
        if command.output.__contains__("Missing device address argument"):  # Means no devices are connected
            return "" if return_as_string else []
        else:
            LOGGER.warning(f"Cannot retrieve bluetooth devices, make sure bluetoothctl is installed")
            return "" if return_as_string else []

    devices = []
    current_device = None

    for line in command.output.split('\n'):
        if line.startswith('Device'):
            if current_device is not None:
                devices.append({
                    "address": current_device,
                    "name": current_name,
                    "connected": current_connected
                })
            current_device = line.split()[1]
            current_name = None
            current_connected = None
        elif 'Name:' in line:
            current_name = line.split(': ', 1)[1]
        elif 'Connected:' in line:
            current_connected = line.split(': ')[1] == 'yes'

    # Add the last device if any
    if current_device is not None:
        devices.append({
            "address": current_device,
            "name": current_name,
            "connected": current_connected
        })

    if connected_devices_only:
        devices = [device for device in devices if device["connected"] == "yes"]

    return devices
