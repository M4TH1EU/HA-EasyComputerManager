import asyncio
import paramiko
from typing import Optional

from custom_components.easy_computer_manager import LOGGER


class SSHClient:
    def __init__(self, host, username, password, port):
        self.host = host
        self.username = username
        self._password = password
        self.port = port
        self._connection = None

    async def connect(self, retried: bool = False, computer: Optional['Computer'] = None) -> None:
        """Open an SSH connection using Paramiko asynchronously."""
        self.disconnect()

        loop = asyncio.get_running_loop()

        try:
            # Create the SSH client
            client = paramiko.SSHClient()

            # Set missing host key policy to automatically accept unknown host keys
            # client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Offload the blocking connect call to a thread
            await loop.run_in_executor(None, self._blocking_connect, client)
            self._connection = client

        except (OSError, paramiko.SSHException) as exc:
            if retried:
                await self.connect(retried=True)
            else:
                LOGGER.debug(f"Failed to connect to {self.host}: {exc}")
        finally:
            if computer is not None:
                if hasattr(computer, "initialized"):
                    computer.initialized = True

    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _blocking_connect(self, client):
        """Perform the blocking SSH connection using Paramiko."""
        client.connect(
            self.host,
            username=self.username,
            password=self._password,
            port=self.port
        )

    async def execute_command(self, command: str) -> tuple[int, str, str]:
        """Execute a command on the SSH server asynchronously."""
        try:
            stdin, stdout, stderr = self._connection.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()

            return exit_status, stdout.read().decode(), stderr.read().decode()
        except (paramiko.SSHException, EOFError) as exc:
            LOGGER.debug(f"Failed to execute command on {self.host}: {exc}")

    def is_connection_alive(self) -> bool:
        """Check if the connection is still alive asynchronously."""
        # use the code below if is_active() returns True
        if self._connection is None:
            return False

        try:
            transport = self._connection.get_transport()
            transport.send_ignore()
            return True
        except EOFError:
            return False
