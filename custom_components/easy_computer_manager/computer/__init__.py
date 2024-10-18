import asyncio
from typing import Optional, Dict, Any

from wakeonlan import send_magic_packet

from custom_components.easy_computer_manager import const, LOGGER
from custom_components.easy_computer_manager.computer.common import OSType, CommandOutput
from custom_components.easy_computer_manager.computer.formatter import format_gnome_monitors_args, format_pactl_commands
from custom_components.easy_computer_manager.computer.parser import parse_gnome_monitors_output, parse_pactl_output, \
    parse_bluetoothctl
from custom_components.easy_computer_manager.computer.ssh_client import SSHClient


class Computer:
    def __init__(self, host: str, mac: str, username: str, password: str, port: int = 22,
                 dualboot: bool = False) -> None:
        """Initialize the Computer object."""
        self.initialized = False  # used to avoid duplicated ssh connections

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

        self._connection: SSHClient = SSHClient(host, username, password, port)
        asyncio.create_task(self._connection.connect(computer=self))

    async def update(self) -> None:
        """Update computer details."""

        async def update_operating_system():
            self.operating_system = await self._detect_operating_system()

        async def update_operating_system_version():
            self.operating_system_version = (await self.run_action("operating_system_version")).output

        async def update_desktop_environment():
            self.desktop_environment = (await self.run_action("desktop_environment")).output.lower()

        async def update_windows_entry_grub():
            self.windows_entry_grub = (await self.run_action("get_windows_entry_grub")).output

        async def update_monitors_config():
            monitors_config = (await self.run_action("get_monitors_config")).output
            if self.operating_system == OSType.LINUX:
                # TODO: add compatibility for KDE/others
                self.monitors_config = parse_gnome_monitors_output(monitors_config)
            elif self.operating_system == OSType.WINDOWS:
                # TODO: implement for Windows
                pass

        async def update_audio_config():
            speakers_config = (await self.run_action("get_speakers")).output
            microphones_config = (await self.run_action("get_microphones")).output

            if self.operating_system == OSType.LINUX:
                self.audio_config = parse_pactl_output(speakers_config, microphones_config)
            elif self.operating_system == OSType.WINDOWS:
                # TODO: implement for Windows
                pass

        async def update_bluetooth_devices():
            bluetooth_config = await self.run_action("get_bluetooth_devices")
            if self.operating_system == OSType.LINUX:
                self.bluetooth_devices = parse_bluetoothctl(bluetooth_config)
            elif self.operating_system == OSType.WINDOWS:
                # TODO: implement for Windows
                pass

        # Reconnect if connection is lost and init is already done
        if self.initialized and not self._connection.is_connection_alive():
            await self._connection.connect()

        if self._connection.is_connection_alive():
            await update_operating_system()
            await update_operating_system_version()
            await update_desktop_environment()
            await update_windows_entry_grub()
            await update_monitors_config()
            await update_audio_config()
            await update_bluetooth_devices()

    async def _detect_operating_system(self) -> OSType:
        """Detect the operating system of the computer."""
        uname_result = await self.run_manually("uname")
        return OSType.LINUX if uname_result.successful() else OSType.WINDOWS

    def is_windows(self) -> bool:
        """Check if the computer is running Windows."""
        return self.operating_system == OSType.WINDOWS

    def is_linux(self) -> bool:
        """Check if the computer is running Linux."""
        return self.operating_system == OSType.LINUX

    async def is_on(self, timeout: int = 1) -> bool:
        """Check if the computer is on by pinging it."""
        ping_cmd = ["ping", "-c", "1", "-W", str(timeout), str(self.host)]
        proc = await asyncio.create_subprocess_exec(
            *ping_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return proc.returncode == 0

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

    async def set_monitors_config(self, monitors_config: Dict[str, Any]) -> None:
        """Change the monitors configuration."""
        if self.is_linux():
            # TODO: other DE support
            if self.desktop_environment == 'gnome':
                await self.run_action("set_monitors_config",
                                      params={"args": format_gnome_monitors_args(monitors_config)})

    async def set_audio_config(self, volume: int | None = None, mute: bool | None = None,
                               input_device: str | None = None,
                               output_device: str | None = None) -> None:
        """Change the audio configuration."""
        if self.is_linux():
            # TODO: other DE support
            if self.desktop_environment == 'gnome':
                pactl_commands = format_pactl_commands(self.audio_config, volume, mute, input_device, output_device)
                for command in pactl_commands:
                    await self.run_action("set_audio_config", params={"args": command})

    async def install_nircmd(self) -> None:
        """Install NirCmd tool (Windows specific)."""
        await self.run_action("install_nircmd", params={"download_url": "https://www.nirsoft.net/utils/nircmd.zip",
                                                        "install_path": f"C:\\Users\\{self.username}\\AppData\\Local\\EasyComputerManager"})

    async def steam_big_picture(self, action: str) -> None:
        """Start, stop or exit Steam Big Picture mode."""
        await self.run_action(f"{action}_steam_big_picture")

    async def run_action(self, id: str, params=None, raise_on_error: bool = None) -> CommandOutput:
        """Run a predefined command via SSH."""
        if params is None:
            params = {}
        if id not in const.ACTIONS:
            return CommandOutput("", 1, "", "Action not found")

        action = const.ACTIONS[id]

        if self.operating_system.lower() in action:
            raise_on_error = action.get("raise_on_error", raise_on_error)

            os_data = action.get(self.operating_system.lower())
            if isinstance(os_data, list):
                commands = os_data
                req_params = []
            elif isinstance(os_data, dict):
                if "command" in os_data or "commands" in os_data:
                    commands = os_data.get("commands", [os_data.get("command")])
                    req_params = os_data.get("params", [])
                    raise_on_error = os_data.get("raise_on_error", raise_on_error)
                elif self.desktop_environment in os_data:
                    commands = os_data.get(self.desktop_environment).get("commands", [
                        os_data.get(self.desktop_environment).get("command")])
                    req_params = os_data.get(self.desktop_environment).get("params", [])
                    raise_on_error = os_data.get(self.desktop_environment).get("raise_on_error", raise_on_error)
                else:
                    raise ValueError(f"Action {id} not supported for DE: {self.desktop_environment}")
            else:
                raise ValueError(f"Action {id} misconfigured/bad format")

            if sorted(req_params) != sorted(params.keys()):
                raise ValueError(f"Invalid/missing parameters for action: {id}")

            command_result = None
            for command in commands:
                for param, value in params.items():
                    command = command.replace(f"%{param}%", value)

                command_result = await self.run_manually(command)
                if command_result.successful():
                    LOGGER.debug(f"Command successful: {command}")
                    return command_result
                else:
                    LOGGER.debug(f"Command failed (raise: {raise_on_error}) : {command}")
                    if raise_on_error:
                        raise ValueError(f"Command failed: {command}")

            return command_result

        else:
            raise ValueError(f"Action {id} not supported for OS: {self.operating_system}")

    async def run_manually(self, command: str) -> CommandOutput:
        """Run a custom command manually via SSH."""
        result = await self._connection.execute_command(command)

        return CommandOutput(command, result[0], result[1], result[2])
