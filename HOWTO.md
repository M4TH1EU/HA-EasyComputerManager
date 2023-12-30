# Quick documentation

## `send_magic_packet`

### Description

Send a 'magic packet' to wake up a device with 'Wake-On-LAN' capabilities.

### Fields

- `mac`
    - **Name:** MAC address
    - **Description:** MAC address of the device to wake up.
    - **Required:** true
    - **Example:** "aa:bb:cc:dd:ee:ff"
    - **Input:** text

- `broadcast_address`
    - **Name:** Broadcast address
    - **Description:** Broadcast IP where to send the magic packet.
    - **Example:** 192.168.255.255
    - **Input:** text

- `broadcast_port`
    - **Name:** Broadcast port
    - **Description:** Port where to send the magic packet.
    - **Default:** 9
    - **Input:** number
        - **Min:** 1
        - **Max:** 65535

## `restart_to_windows_from_linux`

### Description

Restart the computer to Windows when running Linux using Grub.

### Target

- **Device Integration:** easy_computer_manage

## `restart_to_linux_from_windows`

### Description

Restart the computer to Linux when running Windows.

### Target

- **Device Integration:** easy_computer_manage

## `start_computer_to_windows`

### Description

Start the computer directly to Windows (boots to Linux, set grub reboot, then boots to Windows).

### Target

- **Device Integration:** easy_computer_manage

## `put_computer_to_sleep`

### Description

Put the computer to sleep.

### Target

- **Device Integration:** easy_computer_manage

## `restart_computer`

### Description

Restart the computer.

### Target

- **Device Integration:** easy_computer_manage

## `change_monitors_config`

### Description

Change monitors config.

### Target

- **Device Integration:** easy_computer_manage

### Fields

- `monitors_config`
    - **Name:** Monitors config
    - **Description:** Monitors config.
    - **Required:** true
    - **Selector:** object (yaml)
    - **Example:**
      ```yaml
      # Tip: You can use the command `gnome-monitor-config list` or `xrandr` to your monitors names and resolutions.
      HDMI-1:
        enabled: true
        primary: true
        position: [ 0, 0 ]
        mode: 3840x2160@120.000
        transform: normal
        scale: 2
      ```



## `steam_big_picture`

### Description

Start/stop Steam in Big Picture mode or go back to Steam desktop UI.

### Target

- **Device Integration:** easy_computer_manage

### Fields

- `action`
    - **Name:** Action
    - **Description:** Action to perform.
    - **Required:** true
    - **Selector:** select
    - **Options:**
      - **start**: Start Steam in Big Picture mode.
      - **stop**: Stop Steam in Big Picture mode.
      - **exit**: Go back to Steam desktop UI.