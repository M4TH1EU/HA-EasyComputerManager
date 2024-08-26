import re

from custom_components.easy_computer_manager.computer import Computer


async def format_debug_informations(computer: Computer):
    """Return debug information about the host system."""

    data = {
        'os': {
            'name': computer.get_operating_system(),
            'version': computer.get_operating_system_version(),
        },
        'connection':{
            'host': computer.host,
            'mac': computer.mac,
            'username': computer._username,
            'port': computer._port,
            'dualboot': computer._dualboot,
            'is_on': await computer.is_on()
        },
        'grub':{
            'windows_entry': computer.get_windows_entry_grub()
        },
        'audio':{
            'speakers': computer.get_speakers(),
            'microphones': computer.get_microphones()
        },
        'monitors': computer.get_monitors_config(),
        'bluetooth_devices': computer.get_bluetooth_devices()
    }

    return data


def parse_gnome_monitors_config(config: str):
    """Parse the GNOME monitors configuration."""

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
