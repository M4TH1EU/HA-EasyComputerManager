import asyncio
from typing import Optional, Dict, Any

from wakeonlan import send_magic_packet

from custom_components.easy_computer_manager import const, LOGGER
from custom_components.easy_computer_manager.computer.common import OSType, CommandOutput
from custom_components.easy_computer_manager.computer.formatter import format_gnome_monitors_args, format_pactl_commands
from custom_components.easy_computer_manager.computer.parser import parse_gnome_monitors_output, parse_pactl_output, \
    parse_bluetoothctl
from custom_components.easy_computer_manager.computer.ssh_client_paramiko import SSHClient


class Computer:
    def __init__(self, host: str, mac: str, username: str, password: str, port: int = 22,
                 dualboot: bool = False) -> None:
        """Initialize the Computer object."""
        self.initialized = False
        self.host = host
        self.mac = mac
        self.username = username
        self._password = password
        self.port = port
        self.dualboot = dualboot

        self.operating_system: Optional[OSType] = None
        self.operating_system_version: Optional[str] = None
        self.desktop_environment: Optional[str] = None
        self.windows_entry_grub: Optional[str] = None
        self.monitors_config: Optional[Dict[str, Any]] = None
        self.audio_config: Dict[str, Optional[Dict]] = {}
        self.bluetooth_devices: Dict[str, Any] = {}

        self.is_linux = lambda: self.operating_system == OSType.LINUX

        self._connection = SSHClient(host, username, password, port)
        asyncio.create_task(self._initialize_connection())

    async def _initialize_connection(self):
        await self._connection.connect()
        self.initialized = True

    async def update(self, state: Optional[bool] = True, timeout: int = 2) -> None:
        """Update computer details."""
        if not state or not await self.is_on():
            LOGGER.debug("Computer is off, skipping update")
            return

        # Ensure connection is established before updating
        await self._ensure_connection_alive(timeout)

        # Update tasks
        await asyncio.gather(
            self._update_operating_system(),
            self._update_operating_system_version(),
            self._update_desktop_environment(),
            self._update_windows_entry_grub(),
            self._update_monitors_config(),
            self._update_audio_config(),
            self._update_bluetooth_devices()
        )

    async def _ensure_connection_alive(self, timeout: int) -> None:
        """Ensure SSH connection is alive, reconnect if needed."""
        for _ in range(timeout * 4):
            if self._connection.is_connection_alive():
                return
            await asyncio.sleep(0.25)

        if not self._connection.is_connection_alive():
            LOGGER.debug(f"Reconnecting to {self.host}")
            await self._connection.connect()
            if not self._connection.is_connection_alive():
                LOGGER.debug(f"Failed to connect to {self.host} after {timeout}s")
                raise ConnectionError("SSH connection could not be re-established")

    async def _update_operating_system(self) -> None:
        self.operating_system = await self._detect_operating_system()

    async def _update_operating_system_version(self) -> None:
        self.operating_system_version = (await self.run_action("operating_system_version")).output

    async def _update_desktop_environment(self) -> None:
        self.desktop_environment = (await self.run_action("desktop_environment")).output.lower()

    async def _update_windows_entry_grub(self) -> None:
        self.windows_entry_grub = (await self.run_action("get_windows_entry_grub")).output

    async def _update_monitors_config(self) -> None:
        if self.operating_system == OSType.LINUX:
            output = (await self.run_action("get_monitors_config")).output
            self.monitors_config = parse_gnome_monitors_output(output)
        # TODO: Implement for Windows if needed

    async def _update_audio_config(self) -> None:
        speakers_output = (await self.run_action("get_speakers")).output
        microphones_output = (await self.run_action("get_microphones")).output

        if self.operating_system == OSType.LINUX:
            self.audio_config = parse_pactl_output(speakers_output, microphones_output)
        # TODO: Implement for Windows

    async def _update_bluetooth_devices(self) -> None:
        if self.operating_system == OSType.LINUX:
            self.bluetooth_devices = parse_bluetoothctl(await self.run_action("get_bluetooth_devices"))
        # TODO: Implement for Windows

    async def _detect_operating_system(self) -> OSType:
        result = await self.run_manually("uname")
        return OSType.LINUX if result.successful() else OSType.WINDOWS

    async def is_on(self, timeout: int = 1) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", str(timeout), self.host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        return proc.returncode == 0

    async def start(self) -> None:
        send_magic_packet(self.mac)

    async def shutdown(self) -> None:
        await self.run_action("shutdown")

    async def restart(self, from_os: Optional[OSType] = None, to_os: Optional[OSType] = None) -> None:
        # TODO implement from/to os
        await self.run_action("restart")

    async def put_to_sleep(self) -> None:
        """Put the computer to sleep."""
        await self.run_action("sleep")

    async def set_monitors_config(self, monitors_config: Dict[str, Any]) -> None:
        """Set monitors configuration."""
        if self.is_linux() and self.desktop_environment == 'gnome':
            args = format_gnome_monitors_args(monitors_config)
            await self.run_action("set_monitors_config", params={"args": args})

    async def set_audio_config(self, volume: Optional[int] = None, mute: Optional[bool] = None,
                               input_device: Optional[str] = None, output_device: Optional[str] = None) -> None:
        """Set audio configuration."""
        if self.is_linux() and self.desktop_environment == 'gnome':
            pactl_commands = format_pactl_commands(self.audio_config, volume, mute, input_device, output_device)
            for command in pactl_commands:
                await self.run_action("set_audio_config", params={"args": command})

    async def install_nircmd(self) -> None:
        """Install NirCmd tool (Windows specific)."""
        install_path = f"C:\\Users\\{self.username}\\AppData\\Local\\EasyComputerManager"
        await self.run_action("install_nircmd", params={
            "download_url": "https://www.nirsoft.net/utils/nircmd.zip",
            "install_path": install_path
        })

    async def steam_big_picture(self, action: str) -> None:
        """Start, stop, or exit Steam Big Picture mode."""
        await self.run_action(f"{action}_steam_big_picture")

    async def run_action(self, id: str, params: Optional[Dict[str, Any]] = None,
                         raise_on_error: bool = False) -> CommandOutput:
        """Run a predefined action via SSH."""
        params = params or {}

        action = const.ACTIONS.get(id)
        if not action:
            LOGGER.error(f"Action {id} not found.")
            return CommandOutput("", 1, "", "Action not found")

        if not self.operating_system:
            self.operating_system = await self._detect_operating_system()

        os_commands = action.get(self.operating_system.lower())
        if not os_commands:
            raise ValueError(f"Action {id} not supported for OS: {self.operating_system}")

        commands = os_commands if isinstance(os_commands, list) else os_commands.get("commands",
                                                                                     [os_commands.get("command")])
        required_params = []
        if "params" in os_commands:
            required_params = os_commands.get("params", [])

        # Validate parameters
        if sorted(required_params) != sorted(params.keys()):
            raise ValueError(f"Invalid/missing parameters for action: {id}")

        result = CommandOutput("", 1, "", "")
        for command in commands:
            for param, value in params.items():
                command = command.replace(f"%{param}%", str(value))

            result = await self.run_manually(command)
            if result.successful():
                return result
            if raise_on_error:
                raise ValueError(f"Command failed: {command}")

        return result

    async def run_manually(self, command: str) -> CommandOutput:
        return await self._connection.execute_command(command)
