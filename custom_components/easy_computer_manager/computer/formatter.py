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
