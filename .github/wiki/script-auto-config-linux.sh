#!/bin/bash

# Ask for HomeAssistant IP
echo "Please enter your HomeAssistant IP address:"
read -r HOMEASSISTANT_IP

# Enable SSH Server
echo "Enabling SSH Server..."
if command -v systemctl &> /dev/null; then
    sudo systemctl enable --now sshd
else
    echo "Systemctl not found. Please enable SSH manually."
fi

# Configure sudoers
echo "Configuring sudoers..."
echo -e "\n# Allow your user to execute specific commands without a password (for EasyComputerManager/HA)" | sudo tee -a /etc/sudoers
echo "$(whoami) ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/init, /usr/bin/systemctl, /usr/sbin/pm-suspend, /usr/bin/awk, /usr/sbin/grub-reboot, /usr/sbin/grub2-reboot" | sudo tee -a /etc/sudoers

# Firewall Configuration
echo "Configuring firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 22
else
    echo "UFW not found. Please configure the firewall manually (if needed)."
fi

# Setup xhost for GUI apps
echo "Configuring persistent xhost for starting GUI apps (like Steam)..."
COMMANDS="xhost +$HOMEASSISTANT_IP; xhost +localhost"
DESKTOP_ENTRY_NAME="EasyComputerManager-AutoStart"
DESKTOP_ENTRY_PATH="$HOME/.config/autostart/$DESKTOP_ENTRY_NAME.desktop"

# Create the desktop entry file for the Desktop Environment to autostart at login every reboot
cat > "$DESKTOP_ENTRY_PATH" <<EOF
[Desktop Entry]
Type=Application
Name=$DESKTOP_ENTRY_NAME
Exec=sh -c '$COMMANDS'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$DESKTOP_ENTRY_PATH"

echo ""
echo "Done! Some features may require a reboot to work including:"
echo " - Starting GUI apps from HomeAssistant"
echo "You can now add your computer to HomeAssistant."
