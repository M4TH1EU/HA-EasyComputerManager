import subprocess as sp

import fabric2
import wakeonlan
from fabric2 import Connection

from custom_components.easy_computer_manager import const, _LOGGER


class OSType:
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class Computer:
    def __init__(self, host: str, mac: str, username: str, password: str, port: int = 22,
                 dualboot: bool = False) -> None:
        """Init computer."""
        self.host = host
        self.mac = mac
        self._username = username
        self._password = password
        self._port = port
        self._dualboot = dualboot

        self._operating_system = None
        self._operating_system_version = None
        self._windows_entry_grub = None
        self._monitors_config = None
        self._audio_config = None
        self._bluetooth_devices = None

        self._connection = None

        self.setup()

    def _open_ssh_connection(self) -> Connection:
        """Open an SSH connection."""
        conf = fabric2.Config()
        conf.run.hide = True
        conf.run.warn = True
        conf.warn = True
        conf.sudo.password = self._password
        conf.password = self._password

        client = Connection(
            host=self.host, user=self._username, port=self._port, connect_timeout=3,
            connect_kwargs={"password": self._password},
            config=conf
        )

        self._connection = client
        return client

    def _close_ssh_connection(self, client: Connection) -> None:
        """Close the SSH connection."""
        if client.is_connected:
            client.close()

    def setup(self):
        """Setup method that opens an SSH connection and keeps it open for subsequent setup commands."""
        client = self._open_ssh_connection()

        # TODO: run commands here
        self._operating_system = OSType.LINUX  # if self.run_manually("uname").return_code == 0 else OSType.WINDOWS  # TODO: improve this
        self._operating_system_version = self.run_action("operating_system_version").output
        self._windows_entry_grub = self.run_action("get_windows_entry_grub").output
        self._monitors_config = {}
        self._audio_config = {'speakers': None, 'microphones': None}
        self._bluetooth_devices = {}

        self._close_ssh_connection(client)

    # Getters
    def is_on(self, timeout: int = 1) -> bool:
        """Check if the computer is on (ping)."""
        ping_cmd = ["ping", "-c", "1", "-W", str(timeout), str(self.host)]
        status = sp.call(ping_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return status == 0

    def get_operating_system(self) -> str:
        """Get the operating system of the computer."""
        return self._operating_system

    def get_operating_system_version(self) -> str:
        """Get the operating system version of the computer."""
        return self._operating_system_version

    def get_windows_entry_grub(self) -> str:
        """Get the Windows entry in the GRUB configuration file."""
        return self._windows_entry_grub

    def get_monitors_config(self) -> str:
        """Get the monitors configuration of the computer."""
        return self._monitors_config

    def get_speakers(self) -> str:
        """Get the audio configuration of the computer."""
        return self._audio_config.speakers

    def get_microphones(self) -> str:
        """Get the audio configuration of the computer."""
        return self._audio_config.microphones

    def get_bluetooth_devices(self, as_str: bool = False) -> str:
        """Get the Bluetooth devices of the computer."""
        return self._bluetooth_devices

    def is_dualboot(self) -> bool:
        """Check if the computer is dualboot."""
        return self._dualboot

    # Actions
    def start(self) -> None:
        """Start the computer."""
        wakeonlan.send_magic_packet(self.mac)

    def shutdown(self) -> None:
        """Shutdown the computer."""
        self.run_action("shutdown")

    def restart(self, from_os: OSType = None, to_os: OSType = None) -> None:
        """Restart the computer."""
        self.run_action("restart")

    def put_to_sleep(self) -> None:
        """Put the computer to sleep."""
        self.run_action("sleep")

    def change_monitors_config(self, monitors_config: dict) -> None:
        pass

    def change_audio_config(self, volume: int | None = None, mute: bool | None = None, input_device: str | None = None,
                            output_device: str | None = None) -> None:
        pass

    def install_nircmd(self) -> None:
        pass

    def start_steam_big_picture(self) -> None:
        pass

    def stop_steam_big_picture(self) -> None:
        pass

    def exit_steam_big_picture(self) -> None:
        pass

    def run_action(self, action: str, params=None) -> dict:
        """Run a command via SSH. Opens a new connection for each command."""
        if params is None:
            params = {}

        if action not in const.COMMANDS:
            _LOGGER.error(f"Invalid action: {action}")
            return {}

        command_template = const.COMMANDS[action]

        # Check if the command has the required parameters
        if "params" in command_template:
            if sorted(command_template["params"]) != sorted(params.keys()):
                raise ValueError("Invalid parameters")

        # Check if the command is available for the operating system
        match self._operating_system:
            case OSType.WINDOWS:
                commands = command_template[OSType.WINDOWS]
            case OSType.LINUX:
                commands = command_template[OSType.LINUX]
            case _:
                raise ValueError("Invalid operating system")

        for command in commands:
            # Replace the parameters in the command
            for param, value in params.items():
                command = command.replace(f"%{param}%", value)

            result = self.run_manually(command)

            if result['return_code'] == 0:
                _LOGGER.debug(f"Command successful: {command}")
                return result
            else:
                _LOGGER.debug(f"Command failed: {command}")

        return {}

    def run_manually(self, command: str) -> dict:
        """Run a command manually (not from predefined commands)."""

        # Open SSH connection, execute command, and close connection
        client = self._open_ssh_connection()
        result = client.run(command)
        self._close_ssh_connection(client)

        return {"output": result.stdout, "error": result.stderr,
                "return_code": result.return_code}
