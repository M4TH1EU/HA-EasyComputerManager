import logging
import re

import fabric2
from fabric2 import Connection
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


# _LOGGER.setLevel(logging.DEBUG)


def create_ssh_connection(host: str, username: str, password: str, port=22):
    """Create an SSH connection to a host using a username and password specified in the config flow."""
    conf = fabric2.Config()
    conf.run.hide = True
    conf.run.warn = True
    conf.warn = True
    conf.sudo.password = password
    conf.password = password

    connection = Connection(
        host=host, user=username, port=port, connect_timeout=3, connect_kwargs={"password": password},
        config=conf
    )

    _LOGGER.info("Successfully created SSH connection to %s using username %s", host, username)

    return connection


def test_connection(connection: Connection):
    """Test the connection to the host by running a simple command."""
    try:
        connection.run('ls')
        return True
    except Exception:
        return False


def is_unix_system(connection: Connection):
    """Return a boolean based on get_operating_system result."""
    return get_operating_system(connection) == "Linux/Unix"


def get_operating_system_version(connection: Connection, is_unix=None):
    """Return the running operating system name and version."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    if is_unix:
        result = connection.run(
            "awk -F'=' '/^NAME=|^VERSION=/{gsub(/\"/, \"\", $2); printf $2\" \"}\' /etc/os-release && echo").stdout
        if result == "":
            result = connection.run("lsb_release -a | awk '/Description/ {print $2, $3, $4}'").stdout

        return result
    else:
        return connection.run(
            'for /f "tokens=1 delims=|" %i in (\'wmic os get Name ^| findstr /B /C:"Microsoft"\') do @echo %i').stdout


def get_operating_system(connection: Connection):
    """Return the running operating system type."""
    # TODO: might be a better way to do this
    result = connection.run("uname")
    if result.return_code == 0:
        return "Linux/Unix"
    else:
        return "Windows/Other"


def shutdown_system(connection: Connection, is_unix=None):
    """Shutdown the system."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    shutdown_commands = {
        "unix": ["sudo shutdown -h now", "sudo init 0", "sudo systemctl poweroff"],
        "windows": ["shutdown /s /t 0", "wmic os where Primary=TRUE call Shutdown"]
    }

    for command in shutdown_commands["unix" if is_unix else "windows"]:
        result = connection.run(command)
        if result.return_code == 0:
            _LOGGER.debug("System shutting down on %s.", connection.host)
            connection.close()
            return

    raise HomeAssistantError(f"Cannot shutdown system running at {connection.host}, all methods failed.")


def restart_system(connection: Connection, is_unix=None):
    """Restart the system."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    restart_commands = {
        "unix": ["sudo shutdown -r now", "sudo init 6", "sudo systemctl reboot"],
        "windows": ["shutdown /r /t 0", "wmic os where Primary=TRUE call Reboot"]
    }

    for command in restart_commands["unix" if is_unix else "windows"]:
        result = connection.run(command)
        if result.return_code == 0:
            _LOGGER.debug("System restarting on %s.", connection.host)
            return

    raise HomeAssistantError(f"Cannot restart system running at {connection.host}, all methods failed.")


def sleep_system(connection: Connection, is_unix=None):
    """Put the system to sleep."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    sleep_commands = {
        "unix": ["sudo systemctl suspend", "sudo pm-suspend"],
        "windows": ["shutdown /h /t 0", "rundll32.exe powrprof.dll,SetSuspendState Sleep"]
    }

    for command in sleep_commands["unix" if is_unix else "windows"]:
        result = connection.run(command)
        if result.return_code == 0:
            _LOGGER.debug("System sleeping on %s.", connection.host)
            return

    raise HomeAssistantError(f"Cannot put system running at {connection.host} to sleep, all methods failed.")


def get_windows_entry_in_grub(connection: Connection):
    """
    Grabs the Windows entry name in GRUB.
    Used later with grub-reboot to specify which entry to boot.
    """
    commands = [
        "sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub/grub.cfg",
        "sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub2/grub.cfg"
    ]

    for command in commands:
        result = connection.run(command)
        if result.return_code == 0 and result.stdout.strip():
            _LOGGER.debug("Found Windows entry in GRUB: " + result.stdout.strip())
            return result.stdout.strip()

    _LOGGER.error("Could not find Windows entry in GRUB for system running at %s.", connection.host)
    return None


def restart_to_windows_from_linux(connection: Connection):
    """Restart a running Linux system to Windows."""

    if not is_unix_system(connection):
        raise HomeAssistantError(f"System running at {connection.host} is not a Linux system.")

    windows_entry = get_windows_entry_in_grub(connection)

    if windows_entry is not None:
        reboot_commands = ["sudo grub-reboot", "sudo grub2-reboot"]

        for reboot_command in reboot_commands:
            result = connection.run(f"{reboot_command} \"{windows_entry}\"")

            if result.return_code == 0:
                _LOGGER.debug("Rebooting to Windows")
                restart_system(connection)
                return

        raise HomeAssistantError(f"Failed to restart system running on {connection.host} to Windows from Linux.")
    else:
        raise HomeAssistantError(f"Could not find Windows entry in grub for system running at {connection.host}.")


def change_monitors_config(connection: Connection, monitors_config: dict):
    """Change monitors configuration on the host (Linux + Gnome, and partial Windows support)."""

    if is_unix_system(connection):
        command_parts = ["gnome-monitor-config", "set"]

        for monitor, settings in monitors_config.items():
            if settings.get('enabled', False):
                command_parts.extend(['-LpM' if settings.get('primary', False) else '-LM', monitor])

                if 'position' in settings:
                    command_parts.extend(['-x', str(settings["position"][0]), '-y', str(settings["position"][1])])

                if 'mode' in settings:
                    command_parts.extend(['-m', settings["mode"]])

                if 'scale' in settings:
                    command_parts.extend(['-s', str(settings["scale"])])

                if 'transform' in settings:
                    command_parts.extend(['-t', settings["transform"]])

        command = ' '.join(command_parts)
        _LOGGER.debug("Running command: %s", command)

        result = connection.run(command)

        if result.return_code == 0:
            _LOGGER.info("Successfully changed monitors config on system running on %s.", connection.host)

            # Run it once again, it fixes some strange Gnome display bug sometimes and it doesn't hurt
            connection.run(command)
        else:
            raise HomeAssistantError("Could not change monitors config on system running on %s, check logs with debug",
                                     connection.host)

    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")

        # TODO: Implement Windows support using NIRCMD
        command_parts = ["nircmd.exe", "setdisplay"]
        #  setdisplay {monitor:index/name} [width] [height] [color bits] {refresh rate} {-updatereg} {-allusers}

        for monitor, settings in monitors_config.items():
            if settings.get('enabled', False):
                command_parts.extend(
                    [f'{monitor} -primary' if settings.get('primary', False) else f'{monitor} -secondary'])

                if 'resolution' in settings:
                    command_parts.extend([str(settings["resolution"][0]), str(settings["resolution"][1])])

                if 'refresh_rate' in settings:
                    command_parts.extend(['-hz', str(settings["refresh_rate"])])

                if 'color_bits' in settings:
                    command_parts.extend(['-bits', str(settings["color_bits"])])

        command = ' '.join(command_parts)
        _LOGGER.debug("Running command: %s", command)

        result = connection.run(command)

        if result.return_code == 0:
            _LOGGER.info("Successfully changed monitors config on system running on %s.", connection.host)
        else:
            raise HomeAssistantError("Could not change monitors config on system running on %s, check logs with debug",
                                     connection.host)


def silent_install_nircmd(connection: Connection):
    """Silently install NIRCMD on a Windows system."""

    if not is_unix_system(connection):
        download_url = "https://www.nirsoft.net/utils/nircmd.zip"
        install_path = f"C:\\Users\\{connection.user}\\AppData\\Local\\EasyComputerManager"

        # Download and unzip NIRCMD
        download_command = f"powershell -Command \"Invoke-WebRequest -Uri {download_url} -OutFile {install_path}\\nircmd.zip -UseBasicParsing\""
        unzip_command = f"powershell -Command \"Expand-Archive {install_path}\\nircmd.zip -DestinationPath {install_path}\""
        remove_zip_command = f"powershell -Command \"Remove-Item {install_path}\\nircmd.zip\""

        commands = [download_command, unzip_command, remove_zip_command]

        for command in commands:
            result = connection.run(command)
            if result.return_code != 0:
                _LOGGER.error("Could not install NIRCMD on system running on %s.", connection.host)
                return


def get_monitors_config(connection: Connection) -> dict:
    """Parse the output of the gnome-monitor-config command to get the current monitor configuration."""

    if is_unix_system(connection):
        result = connection.run("gnome-monitor-config list")
        if result.return_code != 0:
            raise HomeAssistantError(f"Could not get monitors config on system running at {connection.host}.")

        monitors = []
        current_monitor = None

        for line in result.stdout.split('\n'):
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
    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")


def steam_big_picture(connection: Connection, action: str):
    """Controls Steam in Big Picture mode on the host."""

    _LOGGER.debug(f"Running Steam Big Picture action {action} on system running at {connection.host}.")

    steam_commands = {
        "start": {
            "unix": "export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -bigpicture &",
            "windows": "start steam://open/bigpicture"
        },
        "stop": {
            "unix": "export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -shutdown &",
            "windows": "C:\\Program Files (x86)\\Steam\\steam.exe -shutdown"
            # TODO: check for different Steam install paths
        },
        "exit": {
            "unix": None,  # TODO: find a way to exit Steam Big Picture
            "windows": "nircmd win close title \"Steam Big Picture Mode\""
            # TODO: need to test (thx @MasterHidra https://www.reddit.com/r/Steam/comments/5c9l20/comment/k5fmb3k)
        }
    }

    command = steam_commands.get(action)

    if command is None:
        raise HomeAssistantError(
            f"Invalid action {action} for Steam Big Picture on system running at {connection.host}.")

    if is_unix_system(connection):
        result = connection.run(command.get("unix"))
    else:
        result = connection.run(command.get("windows"))

    if result.return_code != 0:
        raise HomeAssistantError(f"Could not {action} Steam Big Picture on system running at {connection.host}.")


def get_audio_config(connection: Connection):
    if is_unix_system(connection):
        config = {'sinks': [], 'sources': []}

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

        # Get sinks
        result = connection.run("LANG=en_US.UTF-8 pactl list sinks")
        if result.return_code != 0:
            raise HomeAssistantError(f"Could not get audio sinks on system running at {connection.host}.")
        config['sinks'] = parse_device_info(result.stdout.split('\n'), 'Sink')

        # Get sources
        result = connection.run("LANG=en_US.UTF-8 pactl list sources")
        if result.return_code != 0:
            raise HomeAssistantError(f"Could not get audio sources on system running at {connection.host}.")
        config['sources'] = parse_device_info(result.stdout.split('\n'), 'Source')

        return config
    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")


def change_audio_config(connection: Connection, volume: int, mute: bool, input_device: str = "@DEFAULT_SOURCE@",
                        output_device: str = "@DEFAULT_SINK@"):
    """Change audio configuration on the host system."""

    if is_unix_system(connection):
        current_config = get_audio_config(connection)
        executable = "pactl"
        commands = []

        def get_device_id(device_type, user_device):
            for device in current_config[device_type]:
                if device['description'] == user_device:
                    return device['name']
            return user_device

        # Set default sink and source if not specified
        if not output_device:
            output_device = "@DEFAULT_SINK@"
        if not input_device:
            input_device = "@DEFAULT_SOURCE@"

        # Set default sink if specified
        if output_device and output_device != "@DEFAULT_SINK@":
            output_device = get_device_id('sinks', output_device)
            commands.append(f"{executable} set-default-sink {output_device}")

        # Set default source if specified
        if input_device and input_device != "@DEFAULT_SOURCE@":
            input_device = get_device_id('sources', input_device)
            commands.append(f"{executable} set-default-source {input_device}")

        # Set sink volume if specified
        if volume is not None:
            commands.append(f"{executable} set-sink-volume {output_device} {volume}%")

        # Set sink and source mute status if specified
        if mute is not None:
            commands.append(f"{executable} set-sink-mute {output_device} {'yes' if mute else 'no'}")
            commands.append(f"{executable} set-source-mute {input_device} {'yes' if mute else 'no'}")

        # Execute commands
        for command in commands:
            _LOGGER.debug("Running command: %s", command)
            result = connection.run(command)

            if result.return_code != 0:
                raise HomeAssistantError(
                    f"Could not change audio config on system running on {connection.host}, check logs with debug")
    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")


def get_debug_info(connection: Connection):
    """Return debug information about the host system."""

    data = {}

    data_os = {
        'name': get_operating_system(connection),
        'version': get_operating_system_version(connection),
        'is_unix': is_unix_system(connection)
    }

    data_ssh = {
        'is_connected': connection.is_connected,
        'username': connection.user,
        'host': connection.host,
        'port': connection.port
    }

    data_grub = {
        'windows_entry': get_windows_entry_in_grub(connection)
    }

    data_audio = {
        'speakers': get_audio_config(connection).get('sinks'),
        'microphones': get_audio_config(connection).get('sources')
    }

    data['os'] = data_os
    data['ssh'] = data_ssh
    data['grub'] = data_grub
    data['audio'] = data_audio
    data['monitors'] = get_monitors_config(connection)

    return data

def get_bluetooth_devices(connection: Connection, only_connected: bool = False, return_as_string: bool = False):
    commands = {
        "unix": "bash -c \'bluetoothctl info\'",
        "windows": "",
    }

    if is_unix_system(connection):
        result = connection.run(commands["unix"])
        if result.return_code != 0:
            # _LOGGER.debug(f"No bluetooth devices connected or impossible to retrieve them at {connection.host}.")
            return []

        devices = []
        current_device = None

        for line in result.stdout.split('\n'):
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

        if only_connected:
            devices = [device for device in devices if device["connected"] == "yes"]

        if return_as_string:
            devices = "; ".join([f"{device['name']} ({device['address']})" for device in devices])

        return devices
    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")