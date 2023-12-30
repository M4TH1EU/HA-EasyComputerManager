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
            result = connection.run(
                "lsb_release -a | awk '/Description/ {print $2, $3, $4}'"
            ).stdout

        return result
    else:
        return connection.run(
            'for /f "tokens=1 delims=|" %i in (\'wmic os get Name ^| findstr /B /C:"Microsoft"\') do @echo %i'
        ).stdout


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

    if is_unix:
        # First method using shutdown command
        result = connection.run("sudo shutdown -h now")
        if result.return_code != 0:
            # Try a second method using init command
            result = connection.run("sudo init 0")
            if result.return_code != 0:
                # Try a third method using systemctl command
                result = connection.run("sudo systemctl poweroff")
                if result.return_code != 0:
                    raise HomeAssistantError(
                        f"Cannot shutdown system running at {connection.host}, all methods failed.")

    else:
        # First method using shutdown command
        result = connection.run("shutdown /s /t 0")
        if result.return_code != 0:
            # Try a second method using init command
            result = connection.run("wmic os where Primary=TRUE call Shutdown")
            if result.return_code != 0:
                raise HomeAssistantError(f"Cannot shutdown system running at {connection.host}, all methods failed.")

    connection.close()


def restart_system(connection: Connection, is_unix=None):
    """Restart the system."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    if is_unix:
        # First method using shutdown command
        result = connection.run("sudo shutdown -r now")
        if result.return_code != 0:
            # Try a second method using init command
            result = connection.run("sudo init 6")
            if result.return_code != 0:
                # Try a third method using systemctl command
                result = connection.run("sudo systemctl reboot")
                if result.return_code != 0:
                    raise HomeAssistantError(f"Cannot restart system running at {connection.host}, all methods failed.")
    else:
        # First method using shutdown command
        result = connection.run("shutdown /r /t 0")
        if result.return_code != 0:
            # Try a second method using wmic command
            result = connection.run("wmic os where Primary=TRUE call Reboot")
            if result.return_code != 0:
                raise HomeAssistantError(f"Cannot restart system running at {connection.host}, all methods failed.")


def sleep_system(connection: Connection, is_unix=None):
    """Put the system to sleep."""

    if is_unix is None:
        is_unix = is_unix_system(connection)

    if is_unix:
        # First method using systemctl command
        result = connection.run("sudo systemctl suspend")
        if result.return_code != 0:
            # Try a second method using pm-suspend command
            result = connection.run("sudo pm-suspend")
            if result.return_code != 0:
                raise HomeAssistantError(
                    f"Cannot put system running at {connection.host} to sleep, all methods failed.")
    else:
        # First method using shutdown command
        result = connection.run("shutdown /h /t 0")
        if result.return_code != 0:
            # Try a second method using rundll32 command
            result = connection.run("rundll32.exe powrprof.dll,SetSuspendState Sleep")
            if result.return_code != 0:
                raise HomeAssistantError(
                    f"Cannot put system running at {connection.host} to sleep, all methods failed.")


def get_windows_entry_in_grub(connection: Connection):
    """
    Grabs the Windows entry name in GRUB.
    Used later with grub-reboot to specify which entry to boot.
    """
    result = connection.run("sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub/grub.cfg")

    if result.return_code == 0:
        _LOGGER.debug("Found Windows entry in grub : " + result.stdout.strip())
    else:
        result = connection.run("sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub2/grub.cfg")
        if result.return_code == 0:
            _LOGGER.debug("Successfully found Windows Grub entry (%s) for system running at %s.", result.stdout.strip(),
                          connection.host)
        else:
            _LOGGER.error("Could not find Windows entry on computer with address %s.")
            return None

    # Check if the entry is valid
    if result.stdout.strip() != "":
        return result.stdout.strip()
    else:
        _LOGGER.error("Could not find Windows entry on computer with address %s.")
        return None


def restart_to_windows_from_linux(connection: Connection):
    """Restart a running Linux system to Windows."""

    if is_unix_system(connection):
        windows_entry = get_windows_entry_in_grub(connection)
        if windows_entry is not None:
            # First method using grub-reboot command
            result = connection.run(f"sudo grub-reboot \"{windows_entry}\"")
            if result.return_code != 0:
                # Try a second method using grub2-reboot command
                result = connection.run(f"sudo grub2-reboot \"{windows_entry}\"")

            # Restart system if successful grub(2)-reboot command
            if result.return_code == 0:
                _LOGGER.debug("Rebooting to Windows")
                restart_system(connection)
            else:
                raise HomeAssistantError(
                    f"Could not restart system running on {connection.host} to Windows from Linux, all methods failed.")
        else:
            raise HomeAssistantError(f"Could not find Windows entry in grub for system running at {connection.host}.")
    else:
        raise HomeAssistantError(f"System running at {connection.host} is not a Linux system.")


def change_monitors_config(connection: Connection, monitors_config: dict):
    """From a YAML config, changes the monitors configuration on the host, only works on Linux and Gnome (for now)."""
    # TODO: Add support for Windows

    if is_unix_system(connection):
        command_parts = ["gnome-monitor-config", "set"]

        for monitor, settings in monitors_config.items():
            if settings.get('enabled', False):
                if 'primary' in settings and settings['primary']:
                    command_parts.append(f'-LpM {monitor}')
                else:
                    command_parts.append(f'-LM {monitor}')

                if 'position' in settings:
                    command_parts.append(f'-x {settings["position"][0]} -y {settings["position"][1]}')

                if 'mode' in settings:
                    command_parts.append(f'-m {settings["mode"]}')

                if 'scale' in settings:
                    command_parts.append(f'-s {settings["scale"]}')

                if 'transform' in settings:
                    command_parts.append(f'-t {settings["transform"]}')

        command = ' '.join(command_parts)

        _LOGGER.debug("Running command: %s", command)
        result = connection.run(command)

        if result.return_code == 0:
            _LOGGER.info("Successfully changed monitors config on system running on %s.", connection.host)
        else:
            raise HomeAssistantError("Could not change monitors config on system running on %s, check logs with debug",
                                     connection.host)
    else:
        raise HomeAssistantError("Not implemented yet for Windows OS.")

        # Use NIRCMD to change monitors config on Windows
        #  setdisplay {monitor:index/name} [width] [height] [color bits] {refresh rate} {-updatereg} {-allusers}
        # TODO: Work in progress

        command_parts = ["nircmd.exe", "setdisplay"]

        for monitor, settings in monitors_config.items():
            if settings.get('enabled', False):
                if 'primary' in settings and settings['primary']:
                    command_parts.append(f'{monitor} -primary')
                else:
                    command_parts.append(f'{monitor} -secondary')

                if 'resolution' in settings:
                    command_parts.append(f'{settings["resolution"][0]} {settings["resolution"][1]}')

                if 'refresh_rate' in settings:
                    command_parts.append(f'-hz {settings["refresh_rate"]}')

                if 'color_bits' in settings:
                    command_parts.append(f'-bits {settings["color_bits"]}')


def silent_install_nircmd(connection: Connection):
    """Silently install NIRCMD on a Windows system."""

    if not is_unix_system(connection):
        download_url = "http://www.nirsoft.net/utils/nircmd.zip"

        # Download NIRCMD and save it in C:\Users\{username}\AppData\Local\EasyComputerManager\nircmd.zip and unzip it
        commands = [
            f"powershell -Command \"Invoke-WebRequest -Uri {download_url} -OutFile ( New-Item -Path \"C:\\Users\\{connection.user}\\AppData\\Local\\EasyComputerManager\\nircmd.zip\" -Force ) -UseBasicParsing\"",
            f"powershell -Command \"Expand-Archive C:\\Users\\{connection.user}\\AppData\\Local\\EasyComputerManager\\nircmd.zip -DestinationPath C:\\Users\\{connection.user}\\AppData\\Local\\EasyComputerManager\\",
            f"powershell -Command \"Remove-Item C:\\Users\\{connection.user}\\AppData\\Local\\EasyComputerManager\\nircmd.zip\""
        ]

        for command in commands:
            result = connection.run(command)
            if result.return_code != 0:
                _LOGGER.error("Could not install NIRCMD on system running on %s.", connection.host)
                return


def parse_gnome_monitor_config(output):
    # SHOULD NOT BE USED YET, STILL IN DEVELOPMENT
    """Parse the output of the gnome-monitor-config command to get the current monitor configuration."""

    monitors = []
    current_monitor = None

    for line in output.split('\n'):
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
                current_monitor['resolutions'].append(resolution_match.group(1))

    if current_monitor:
        monitors.append(current_monitor)

    return monitors


def steam_big_picture(connection: Connection, action: str):
    """Controls Steam in Big Picture mode on the host."""

    _LOGGER.debug(f"Running Steam Big Picture action {action} on system running at {connection.host}.")

    result = None
    match action:
        case "start":
            if is_unix_system(connection):
                result = connection.run("export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -bigpicture &")
            else:
                result = connection.run("start steam://open/bigpicture")
        case "stop":
            if is_unix_system(connection):
                result = connection.run("export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -shutdown &")
            else:
                # TODO: check for different Steam install paths
                result = connection.run("C:\\Program Files (x86)\\Steam\\steam.exe -shutdown")
        case "exit":
            if is_unix_system(connection):
                # TODO: find a way to exit Steam Big Picture
                pass
            else:
                # TODO: need to test (thx @MasterHidra https://www.reddit.com/r/Steam/comments/5c9l20/comment/k5fmb3k)
                result = connection.run("nircmd win close title \"Steam Big Picture Mode\"")
        case _:
            raise HomeAssistantError(
                f"Invalid action {action} for Steam Big Picture on system running at {connection.host}.")

    if result is None or result.return_code != 0:
        raise HomeAssistantError(f"Could not {action} Steam Big Picture on system running at {connection.host}.")
