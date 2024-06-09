#!/bin/bash

# Retrieve the username of the person who invoked sudo
USER_BEHIND_SUDO=$(who am i | awk '{print $1}')

# Function to print colored text
print_colored() {
    local color="$1"
    local text="$2"
    echo -e "${color}${text}\033[0m"
}

# Define colors
COLOR_RED="\033[0;31m"
COLOR_GREEN="\033[0;32m"
COLOR_YELLOW="\033[1;33m"
COLOR_BLUE="\033[0;34m"

# Ask for HomeAssistant IP
print_colored "$COLOR_BLUE" "Please enter your HomeAssistant local IP address (even if behind proxy, need LAN address):"
read -r HOMEASSISTANT_IP

# Enable SSH Server
print_colored "$COLOR_BLUE" "Enabling SSH Server..."
if command -v systemctl &> /dev/null; then
    sudo systemctl enable --now sshd
    print_colored "$COLOR_GREEN" "SSH Server enabled successfully."
else
    print_colored "$COLOR_RED" "Systemctl not found. Please enable SSH manually."
fi

# Configure sudoers
print_colored "$COLOR_BLUE" "Configuring sudoers..."
echo -e "\n# Allow your user to execute specific commands without a password (for EasyComputerManager/HA)" | sudo tee -a /etc/sudoers > /dev/null
echo "$USER_BEHIND_SUDO ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/init, /usr/bin/systemctl, /usr/sbin/pm-suspend, /usr/bin/awk, /usr/sbin/grub-reboot, /usr/sbin/grub2-reboot" | sudo tee -a /etc/sudoers > /dev/null
print_colored "$COLOR_GREEN" "Sudoers file configured successfully."

# Firewall Configuration
print_colored "$COLOR_BLUE" "Configuring firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 22
    print_colored "$COLOR_GREEN" "Firewall configured to allow SSH."
else
    print_colored "$COLOR_RED" "UFW not found. Please configure the firewall manually (if needed)."
fi

# Setup xhost for GUI apps
print_colored "$COLOR_BLUE" "Configuring persistent xhost for starting GUI apps (like Steam)..."
COMMANDS="xhost +$HOMEASSISTANT_IP; xhost +localhost"
DESKTOP_ENTRY_NAME="EasyComputerManager-AutoStart"
DESKTOP_ENTRY_PATH="/home/$USER_BEHIND_SUDO/.config/autostart/$DESKTOP_ENTRY_NAME.desktop"

# Create the desktop entry file for the Desktop Environment to autostart at login every reboot
# cat > "$DESKTOP_ENTRY_PATH" <<EOF
# [Desktop Entry]
# Type=Application
# Name=$DESKTOP_ENTRY_NAME
# Exec=sh -c '$COMMANDS'
# Hidden=false
# NoDisplay=false
# X-GNOME-Autostart-enabled=true
# EOF
# chmod +x "$DESKTOP_ENTRY_PATH"
print_colored "$COLOR_GREEN" "Desktop entry created at $DESKTOP_ENTRY_PATH."

print_colored "$COLOR_GREEN" "\nDone! Some features may require a reboot to work including:"
print_colored "$COLOR_YELLOW" " - Starting GUI apps from HomeAssistant"
print_colored "$COLOR_GREEN" "\nYou can now add your computer to HomeAssistant."
print_colored "$COLOR_RED" "\nWARNING : Don't forget to install these packages : gnome-monitor-config, pactl, bluetoothctl"
