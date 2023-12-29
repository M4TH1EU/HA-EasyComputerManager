import logging
import re

import fabric2
from fabric2 import Connection

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
                    _LOGGER.error("Cannot shutdown system running at %s, all methods failed.", connection.host)

    else:
        # First method using shutdown command
        result = connection.run("shutdown /s /t 0")
        if result.return_code != 0:
            # Try a second method using init command
            result = connection.run("wmic os where Primary=TRUE call Shutdown")
            if result.return_code != 0:
                _LOGGER.error("Cannot shutdown system running at %s, all methods failed.", connection.host)

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
                    _LOGGER.error("Cannot restart system running at %s, all methods failed.", connection.host)
    else:
        # First method using shutdown command
        result = connection.run("shutdown /r /t 0")
        if result.return_code != 0:
            # Try a second method using wmic command
            result = connection.run("wmic os where Primary=TRUE call Reboot")
            if result.return_code != 0:
                _LOGGER.error("Cannot restart system running at %s, all methods failed.", connection.host)


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
                _LOGGER.error("Cannot put system running at %s to sleep, all methods failed.", connection.host)
    else:
        # First method using shutdown command
        result = connection.run("shutdown /h /t 0")
        if result.return_code != 0:
            # Try a second method using rundll32 command
            result = connection.run("rundll32.exe powrprof.dll,SetSuspendState Sleep")
            if result.return_code != 0:
                _LOGGER.error("Cannot put system running at %s to sleep, all methods failed.", connection.host)


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
                _LOGGER.info("Rebooting to Windows")
                restart_system(connection)
            else:
                _LOGGER.error("Could not restart system running on %s to Windows from Linux, all methods failed.",
                              connection.host)
    else:
        _LOGGER.error(
            "Could not restart system running on %s to Windows from Linux, system does not appear to be a Linux-based OS.",
            connection.host)


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
            _LOGGER.error("Could not change monitors config on system running on %s", connection.host)
            # TODO : add useful debug info
    else:
        _LOGGER.error("Not implemented yet.")


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
