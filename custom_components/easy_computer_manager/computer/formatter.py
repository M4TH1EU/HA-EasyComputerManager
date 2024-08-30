def format_gnome_monitors_args(monitors_config: dict):
    args = []

    monitors_config = monitors_config.get('monitors_config', {})

    for monitor, settings in monitors_config.items():
        if settings.get('enabled', False):
            args.extend(['-LpM' if settings.get('primary', False) else '-LM', monitor])

            if 'position' in settings:
                args.extend(['-x', str(settings["position"][0]), '-y', str(settings["position"][1])])

            if 'mode' in settings:
                args.extend(['-m', settings["mode"]])

            if 'scale' in settings:
                args.extend(['-s', str(settings["scale"])])

            if 'transform' in settings:
                args.extend(['-t', settings["transform"]])

    return ' '.join(args)


def format_pactl_commands(current_config: {}, volume: int, mute: bool, input_device: str = "@DEFAULT_SOURCE@",
                          output_device: str = "@DEFAULT_SINK@"):
    """Change audio configuration on the host system."""

    commands = []

    def get_device_id(device_type, user_device):
        for device in current_config[device_type]:
            if device['description'] == user_device:
                return device['name']
        return user_device

    # Set default sink and source if not specified
    if not output_device:
        output_device = "@DEFAULT_SINK@"
    if not input_device:
        input_device = "@DEFAULT_SOURCE@"

    # Set default sink if specified
    if output_device and output_device != "@DEFAULT_SINK@":
        output_device = get_device_id('sinks', output_device)
        commands.append(f"set-default-sink {output_device}")

    # Set default source if specified
    if input_device and input_device != "@DEFAULT_SOURCE@":
        input_device = get_device_id('sources', input_device)
        commands.append(f"set-default-source {input_device}")

    # Set sink volume if specified
    if volume is not None:
        commands.append(f"set-sink-volume {output_device} {volume}%")

    # Set sink and source mute status if specified
    if mute is not None:
        commands.append(f"set-sink-mute {output_device} {'yes' if mute else 'no'}")
        commands.append(f"set-source-mute {input_device} {'yes' if mute else 'no'}")

    return commands
