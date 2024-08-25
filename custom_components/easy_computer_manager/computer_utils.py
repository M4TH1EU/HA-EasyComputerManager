from custom_components.easy_computer_manager.computer import Computer


def get_debug_info(computer: Computer):
    """Return debug information about the host system."""

    data = {
        'os': {
            'name': computer.get_operating_system(),
            'version': computer.get_operating_system_version(),
        },
        'connection':{
            'host': computer.host,
            'mac': computer.mac,
            'username': computer._username,
            'port': computer._port,
            'dualboot': computer._dualboot,
            'is_on': computer.is_on()
        },
        'grub':{
            'windows_entry': computer.get_windows_entry_grub()
        },
        'audio':{
            'speakers': computer.get_speakers(),
            'microphones': computer.get_microphones()
        },
        'monitors': computer.get_monitors_config(),
        'bluetooth_devices': computer.get_bluetooth_devices()
    }

    return data
