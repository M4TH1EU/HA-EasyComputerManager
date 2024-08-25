import subprocess as sp

import paramiko
import wakeonlan

from custom_components.easy_computer_manager import const, _LOGGER


class OSType:
    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "MacOS"


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

        self.setup()

    async def _open_ssh_connection(self):
        """Open an SSH connection."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.host, port=self._port, username=self._username, password=self._password)
        return client

    def _close_ssh_connection(self, client):
        """Close the SSH connection."""
        if client:
            client.close()

    def setup(self):
        """Setup method that opens an SSH connection and keeps it open for subsequent setup commands."""
        client = self._open_ssh_connection()

        # TODO: run commands here
        self._operating_system = OSType.LINUX if self.run_manually(
            "uname").return_code == 0 else OSType.WINDOWS  # TODO: improve this
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

    def run_action(self, command: str, params=None) -> {}:
        """Run a command via SSH. Opens a new connection for each command."""
        if params is None:
            params = {}
        if command not in const.COMMANDS:
            _LOGGER.error(f"Invalid command: {command}")
            return

        command_template = const.COMMANDS[command]

        # Check if the command has the required parameters
        if "params" in command_template:
            if sorted(command_template.params) != sorted(params.keys()):
                raise ValueError("Invalid parameters")

        # Check if the command is available for the operating system
        match self._operating_system:
            case OSType.WINDOWS:
                command = command_template[OSType.WINDOWS]
            case OSType.LINUX:
                command = command_template[OSType.LINUX]
            case _:
                raise ValueError("Invalid operating system")

        # Replace the parameters in the command
        for param in params:
            command = command.replace(f"%{param}%", params[param])

        # Open SSH connection, execute command, and close connection
        client = self._open_ssh_connection()
        stdin, stdout, stderr = client.exec_command(command)
        print(stdout.read().decode())  # Print the command output for debugging
        self._close_ssh_connection(client)

        return {"output": stdout.read().decode(), "error": stderr.read().decode(),
                "return_code": stdout.channel.recv_exit_status()}

    def run_manually(self, command: str) -> {}:
        """Run a command manually (not from predefined commands)."""
        client = self._open_ssh_connection()
        stdin, stdout, stderr = client.exec_command(command)
        print(stdout.read().decode())  # Print the command output for debugging
        self._close_ssh_connection(client)

        return {"output": stdout.read().decode(), "error": stderr.read().decode(),
                "return_code": stdout.channel.recv_exit_status()}
