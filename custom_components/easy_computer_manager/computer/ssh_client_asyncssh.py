from typing import Optional

import asyncssh

from custom_components.easy_computer_manager import LOGGER
from custom_components.easy_computer_manager.computer import CommandOutput


class SSHClient:
    def __init__(self, host: str, username: str, password: Optional[str] = None, port: int = 22):
        self.host = host
        self.username = username
        self._password = password
        self.port = port
        self._connection: Optional[asyncssh.SSHClientConnection] = None
        self._session: Optional[asyncssh.SSHClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.disconnect()

    async def connect(self, retried: bool = False, computer: Optional['Computer'] = None) -> None:
        """Open an SSH connection using AsyncSSH."""
        if self.is_connection_alive():
            LOGGER.debug(f"Connection to {self.host} is already active.")
            return

        await self.disconnect()  # Ensure any previous connection is closed

        try:
            self._connection = await asyncssh.connect(
                host=self.host,
                username=self.username,
                password=self._password,
                port=self.port,
                known_hosts=None  # Automatically accept unknown host keys
            )
            self._session = await self._connection.create_session(asyncssh.SSHClientSession)
            LOGGER.debug(f"Connected to {self.host}")
        except (OSError, asyncssh.Error) as exc:
            LOGGER.debug(f"Failed to connect to {self.host}: {exc}")
            if not retried:
                LOGGER.debug(f"Retrying connection to {self.host}...")
                await self.connect(retried=True)  # Retry only once
        finally:
            if computer is not None and hasattr(computer, "initialized"):
                computer.initialized = True

    async def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._session:
            self._session.close()
            await self._session.wait_closed()
        if self._connection:
            self._connection.close()
            await self._connection.wait_closed()
            LOGGER.debug(f"Disconnected from {self.host}")
        self._connection = None
        self._session = None

    async def execute_command(self, command: str) -> CommandOutput:
        """Execute a command on the SSH server asynchronously using a persistent session."""
        if not self.is_connection_alive():
            LOGGER.debug(f"Connection to {self.host} is not alive. Reconnecting...")
            await self.connect()

        try:
            result = await self._connection.run(command, check=False)
            return CommandOutput(command, result.exit_status, result.stdout, result.stderr)
        except (asyncssh.ProcessError, asyncssh.Error) as exc:
            LOGGER.error(f"Failed to execute command on {self.host}: {exc}")
            return CommandOutput(command, -1, "", "")

    def is_connection_alive(self) -> bool:
        """Check if the SSH connection is still alive."""
        return self._connection is not None and not self._connection.is_closed()
