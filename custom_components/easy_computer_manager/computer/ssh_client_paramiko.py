import asyncio
from typing import Optional

import paramiko

from custom_components.easy_computer_manager import LOGGER
from custom_components.easy_computer_manager.computer import CommandOutput


class SSHClient:
    def __init__(self, host: str, username: str, password: Optional[str] = None, port: int = 22):
        self.host = host
        self.username = username
        self._password = password
        self.port = port
        self._connection: Optional[paramiko.SSHClient] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    async def connect(self, retried: bool = False, computer: Optional['Computer'] = None) -> None:
        """Open an SSH connection using Paramiko asynchronously."""
        if self.is_connection_alive():
            LOGGER.debug(f"Connection to {self.host} is already active.")
            return

        self.disconnect()  # Ensure any previous connection is closed

        loop = asyncio.get_running_loop()
        client = paramiko.SSHClient()

        # Set missing host key policy to automatically accept unknown host keys
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Offload the blocking connect call to a thread
            await loop.run_in_executor(None, self._blocking_connect, client)
            self._connection = client
            LOGGER.debug(f"Connected to {self.host}")

        except (OSError, paramiko.SSHException) as exc:
            LOGGER.debug(f"Failed to connect to {self.host}: {exc}")
            if not retried:
                LOGGER.debug(f"Retrying connection to {self.host}...")
                await self.connect(retried=True)  # Retry only once

        finally:
            if computer is not None and hasattr(computer, "initialized"):
                computer.initialized = True

    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._connection:
            self._connection.close()
            LOGGER.debug(f"Disconnected from {self.host}")
        self._connection = None

    def _blocking_connect(self, client: paramiko.SSHClient):
        """Perform the blocking SSH connection using Paramiko."""
        client.connect(
            hostname=self.host,
            username=self.username,
            password=self._password,
            port=self.port,
            look_for_keys=False,  # Set this to True if using private keys
            allow_agent=False
        )

    async def execute_command(self, command: str) -> CommandOutput:
        """Execute a command on the SSH server asynchronously."""
        if not self.is_connection_alive():
            LOGGER.debug(f"Connection to {self.host} is not alive. Reconnecting...")
            await self.connect()

        try:
            # Offload command execution to avoid blocking
            loop = asyncio.get_running_loop()
            stdin, stdout, stderr = await loop.run_in_executor(None, self._connection.exec_command, command)

            exit_status = stdout.channel.recv_exit_status()
            return CommandOutput(command, exit_status, stdout.read().decode(), stderr.read().decode())

        except (paramiko.SSHException, EOFError) as exc:
            LOGGER.error(f"Failed to execute command on {self.host}: {exc}")
            return CommandOutput(command, -1, "", "")

    def is_connection_alive(self) -> bool:
        """Check if the SSH connection is still alive."""
        if self._connection is None:
            return False

        try:
            transport = self._connection.get_transport()
            transport.send_ignore()

            self._connection.exec_command('ls', timeout=1)
            return True

        except Exception as e:
            return False
