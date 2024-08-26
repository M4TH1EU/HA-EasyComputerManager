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
        "linux": [
            "echo \"${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-$(basename $(grep -Eo \'exec .*(startx|xinitrc)\' ~/.xsession 2>/dev/null | awk \'{print $2}\'))}}\""],
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
        "params": ["grub-entry"],
        "linux": ["sudo grub-reboot %grub-entry%", "sudo grub2-reboot %grub-entry%"]
    },
    "get_monitors_config": {
        "linux": ["gnome-monitor-config list"]
    },
    "get_speakers": {
        "linux": ["LANG=en_US.UTF-8 pactl list sinks"]
    },
    "get_microphones": {
        "linux": ["LANG=en_US.UTF-8 pactl list sources"]
    },
    "get_bluetooth_devices": {
        "exit": False,
        "linux": ["bluetoothctl info"]
    }
}