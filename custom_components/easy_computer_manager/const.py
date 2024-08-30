"""Constants for the Easy Computer Manager integration."""

DOMAIN = "easy_computer_manager"
SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"
SERVICE_RESTART_TO_WINDOWS_FROM_LINUX = "restart_to_windows_from_linux"
SERVICE_RESTART_TO_LINUX_FROM_WINDOWS = "restart_to_linux_from_windows"
SERVICE_PUT_COMPUTER_TO_SLEEP = "put_computer_to_sleep"
SERVICE_START_COMPUTER_TO_WINDOWS = "start_computer_to_windows"
SERVICE_RESTART_COMPUTER = "restart_computer"
SERVICE_CHANGE_MONITORS_CONFIG = "change_monitors_config"
SERVICE_STEAM_BIG_PICTURE = "steam_big_picture"
SERVICE_CHANGE_AUDIO_CONFIG = "change_audio_config"
SERVICE_DEBUG_INFO = "debug_info"


ACTIONS = {
    "operating_system": {
        "linux": ["uname"]
    },
    "operating_system_version": {
        "windows": ['for /f "tokens=1 delims=|" %i in (\'wmic os get Name ^| findstr /B /C:"Microsoft"\') do @echo %i'],
        "linux": ["awk -F'=' '/^NAME=|^VERSION=/{gsub(/\"/, \"\", $2); printf $2\" \"}\' /etc/os-release && echo", "lsb_release -a | awk '/Description/ {print $2, $3, $4}'"]
    },
    "desktop_environment": {
        "linux": ["for session in $(ls /usr/bin/*session 2>/dev/null); do basename $session | sed 's/-session//'; done | grep -E 'gnome|kde|xfce|mate|lxde|cinnamon|budgie|unity' | head -n 1"],
        "windows": ["echo Windows"]
    },
    "shutdown": {
        "windows": ["shutdown /s /t 0", "wmic os where Primary=TRUE call Shutdown"],
        "linux": ["sudo shutdown -h now", "sudo init 0", "sudo systemctl poweroff"]
    },
    "restart": {
        "windows": ["shutdown /r /t 0", "wmic os where Primary=TRUE call Reboot"],
        "linux": ["sudo shutdown -r now", "sudo init 6", "sudo systemctl reboot"]
    },
    "sleep": {
        "windows": ["shutdown /h /t 0", "rundll32.exe powrprof.dll,SetSuspendState Sleep"],
        "linux": ["sudo systemctl suspend", "sudo pm-suspend"]
    },
    "get_windows_entry_grub": {
        "linux": ["sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub/grub.cfg",
                  "sudo awk -F \"'\" '/windows/ {print $2}' /boot/grub2/grub.cfg"]
    },
    "set_grub_entry": {
        "linux": {
            "commands": ["sudo grub-reboot %grub-entry%", "sudo grub2-reboot %grub-entry%"],
            "params": ["grub-entry"],
        }
    },
    "get_monitors_config": {
        "linux": ["gnome-monitor-config list"]
    },
    "set_monitors_config": {
        "linux": {
            "gnome": {
                "command": "gnome-monitor-config set %args%",
                "params": ["args"]
            }
        }
    },
    "get_speakers": {
        "linux": ["LANG=en_US.UTF-8 pactl list sinks"]
    },
    "get_microphones": {
        "linux": ["LANG=en_US.UTF-8 pactl list sources"]
    },
    "set_audio_config": {
        "linux": {
            "command": "LANG=en_US.UTF-8 pactl %args%",
            "params": ["args"]
        }
    },
    "get_bluetooth_devices": {
        "linux": {
            "command": "bluetoothctl info",
            "raise_on_error": False,
        }
    },
    "install_nirmcd": {
        "windows": {
            "command": "powershell -Command \"Invoke-WebRequest -Uri %download_url% -OutFile %install_path%\\nircmd.zip -UseBasicParsing; Expand-Archive %install_path%\\nircmd.zip -DestinationPath %install_path%; Remove-Item %install_path%\\nircmd.zip\"",
            "params": ["download_url", "install_path"]
        }
    },
    "start_steam_big_picture": {
        "linux": "export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -bigpicture &",
        "windows": "start steam://open/bigpicture"
    },
    "stop_steam_big_picture": {
        "linux": "export WAYLAND_DISPLAY=wayland-0; export DISPLAY=:0; steam -shutdown &",
        "windows": "C:\\Program Files (x86)\\Steam\\steam.exe -shutdown"
    },
    "exit_steam_big_picture": {
        "linux": "",  # TODO: find a way to exit steam big picture
        "windows": "nircmd win close title \"Steam Big Picture Mode\""
    },
}