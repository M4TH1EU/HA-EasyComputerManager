from enum import Enum


class OSType(str, Enum):
    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "MacOS"


class CommandOutput:
    def __init__(self, command: str, return_code: int, output: str, error: str) -> None:
        self.command = command
        self.return_code = return_code
        self.output = output.strip()
        self.error = error.strip()

    def successful(self) -> bool:
        return self.return_code == 0
