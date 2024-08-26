import asyncio

import asyncssh
from custom_components.easy_computer_manager import const, _LOGGER
from wakeonlan import send_magic_packet


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

        asyncio.create_task(self.update())

    async def _open_ssh_connection(self) -> asyncssh.SSHClientConnection:
        """Open an asynchronous SSH connection."""
        try:
            client = await asyncssh.connect(
                self.host,
                username=self._username,
                password=self._password,
                port=self._port,
                known_hosts=None
            )
            return client
        except (OSError, asyncssh.Error) as exc:
            _LOGGER.error(f"SSH connection failed: {exc}")
            return None

    async def _close_ssh_connection(self, client: asyncssh.SSHClientConnection) -> None:
        """Close the SSH connection."""
        client.close()

    async def update(self) -> None:
        """Setup method that opens an SSH connection and runs setup commands asynchronously."""
        client = await self._open_ssh_connection()
        if not client:
            return

        self._operating_system = OSType.LINUX if (await self.run_manually("uname")).get(
            "return_code") == 0 else OSType.WINDOWS  # TODO: improve this
        self._operating_system_version = (await self.run_action("operating_system_version")).get("output")
        self._windows_entry_grub = (await self.run_action("get_windows_entry_grub")).get("output")
        self._monitors_config = {}
        self._audio_config = {'speakers': None, 'microphones': None}
        self._bluetooth_devices = {}

        await self._close_ssh_connection(client)

    # Getters
    async def is_on(self, timeout: int = 1) -> bool:
        """Check if the computer is on (ping)."""
        ping_cmd = ["ping", "-c", "1", "-W", str(timeout), str(self.host)]
        proc = await asyncio.create_subprocess_exec(
            *ping_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return proc.returncode == 0

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
        return self._audio_config.get("speakers")

    def get_microphones(self) -> str:
        """Get the audio configuration of the computer."""
        return self._audio_config.get("microphones")

    def get_bluetooth_devices(self, as_str: bool = False) -> str:
        """Get the Bluetooth devices of the computer."""
        return self._bluetooth_devices

    def is_dualboot(self) -> bool:
        """Check if the computer is dualboot."""
        return self._dualboot

    # Actions
    async def start(self) -> None:
        """Start the computer."""
        send_magic_packet(self.mac)

    async def shutdown(self) -> None:
        """Shutdown the computer."""
        await self.run_action("shutdown")

    async def restart(self, from_os: OSType = None, to_os: OSType = None) -> None:
        """Restart the computer."""
        await self.run_action("restart")

    async def put_to_sleep(self) -> None:
        """Put the computer to sleep."""
        await self.run_action("sleep")

    async def change_monitors_config(self, monitors_config: dict) -> None:
        pass

    async def change_audio_config(self, volume: int | None = None, mute: bool | None = None,
                                  input_device: str | None = None,
                                  output_device: str | None = None) -> None:
        pass

    async def install_nircmd(self) -> None:
        pass

    async def start_steam_big_picture(self) -> None:
        pass

    async def stop_steam_big_picture(self) -> None:
        pass

    async def exit_steam_big_picture(self) -> None:
        pass

    async def run_action(self, action: str, params=None) -> dict:
        """Run a command via SSH. Opens a new connection for each command."""
        if params is None:
            params = {}

        if action in const.COMMANDS:
            command_template = const.COMMANDS[action]

            # Check if the command has the required parameters
            if "params" in command_template:
                if sorted(command_template["params"]) != sorted(params.keys()):
                    raise ValueError("Invalid parameters")

            # Check if the command is available for the operating system
            if self._operating_system in command_template:
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

                    result = await self.run_manually(command)

                    if result['return_code'] == 0:
                        _LOGGER.debug(f"Command successful: {command}")
                        return result
                    else:
                        _LOGGER.debug(f"Command failed: {command}")

        return {"output": "", "error": "", "return_code": 1}

    async def run_manually(self, command: str) -> dict:
        """Run a command manually (not from predefined commands)."""

        # Open SSH connection, execute command, and close connection
        client = await self._open_ssh_connection()
        if not client:
            return {"output": "", "error": "SSH connection failed", "return_code": 1}

        result = await client.run(command)
        await self._close_ssh_connection(client)

        return {"output": result.stdout, "error": result.stderr,
                "return_code": result.exit_status}
