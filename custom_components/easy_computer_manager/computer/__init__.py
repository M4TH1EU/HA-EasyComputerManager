import asyncio
from typing import Optional, Dict, Any

import asyncssh
from asyncssh import SSHClientConnection
from wakeonlan import send_magic_packet

from custom_components.easy_computer_manager import const, LOGGER
from custom_components.easy_computer_manager.computer.common import OSType, CommandOutput
from custom_components.easy_computer_manager.computer.utils import parse_gnome_monitors_output, \
    parse_pactl_output, parse_bluetoothctl


class Computer:
    def __init__(self, host: str, mac: str, username: str, password: str, port: int = 22,
                 dualboot: bool = False) -> None:
        """Initialize the Computer object."""
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

        self._connection: Optional[SSHClientConnection] = None

        asyncio.create_task(self.update())

    async def _connect(self) -> None:
        """Open an asynchronous SSH connection."""
        try:
            client = await asyncssh.connect(
                self.host,
                username=self.username,
                password=self._password,
                port=self.port,
                known_hosts=None
            )
            asyncssh.set_log_level("ERROR")
            self._connection = client
        except (OSError, asyncssh.Error) as exc:
            raise ValueError(f"Failed to connect to {self.host}: {exc}")

    async def _renew_connection(self) -> None:
        """Renew the SSH connection if it is closed."""
        if self._connection is None or self._connection.is_closed:
            self._connection = await self._connect()

    async def update(self) -> None:
        """Update computer details."""

        await self._renew_connection()

        async def update_operating_system():
            self.operating_system = await self._detect_operating_system()

        async def update_operating_system_version():
            self.operating_system_version = (await self.run_action("operating_system_version")).output

        async def update_desktop_environment():
            self.desktop_environment = (await self.run_action("desktop_environment")).output

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

    async def change_monitors_config(self, monitors_config: Dict[str, Any]) -> None:
        """Change the monitors configuration."""
        # Implementation needed
        pass

    async def change_audio_config(self, volume: int | None = None, mute: bool | None = None,
                                  input_device: str | None = None,
                                  output_device: str | None = None) -> None:
        """Change the audio configuration."""
        # Implementation needed
        pass

    async def install_nircmd(self) -> None:
        """Install NirCmd tool (Windows specific)."""
        # Implementation needed
        pass

    async def start_steam_big_picture(self) -> None:
        """Start Steam Big Picture mode."""
        # Implementation needed
        pass

    async def stop_steam_big_picture(self) -> None:
        """Stop Steam Big Picture mode."""
        # Implementation needed
        pass

    async def exit_steam_big_picture(self) -> None:
        """Exit Steam Big Picture mode."""
        # Implementation needed
        pass

    async def run_action(self, action: str, params: Dict[str, Any] = None, exit: bool = None) -> CommandOutput:
        """Run a predefined command via SSH."""
        if params is None:
            params = {}

        if action not in const.ACTIONS:
            return CommandOutput("", 1, "", "Action not found")

        command_template = const.ACTIONS[action]

        if "params" in command_template and sorted(command_template["params"]) != sorted(params.keys()):
            raise ValueError(f"Invalid parameters for action: {action}")

        if "exit" in command_template and exit is None:
            exit = command_template["exit"]

        commands = command_template.get(self.operating_system.lower())
        if not commands:
            raise ValueError(f"Action not supported for OS: {self.operating_system}")

        command_result = None
        for command in commands:
            for param, value in params.items():
                command = command.replace(f"%{param}%", value)

            command_result = await self.run_manually(command)
            if command_result.successful():
                LOGGER.debug(f"Command successful: {command}")
                return command_result

            LOGGER.debug(f"Command failed: {command}")

        if exit:
            raise ValueError(f"Failed to run action: {action}")

        return command_result

    async def run_manually(self, command: str) -> CommandOutput:
        """Run a custom command manually via SSH."""
        if not self._connection:
            await self._connect()

        result = await self._connection.run(command)

        return CommandOutput(command, result.exit_status, result.stdout, result.stderr)