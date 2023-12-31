#!/bin/bash

# Enable SSH Server
if command -v systemctl &> /dev/null; then
    sudo systemctl enable --now sshd
else
    echo "Systemctl not found. Please enable SSH manually."
fi

# Configure sudoers
echo "Configuring sudoers..."
echo -e "\n# Allow your user to execute specific commands without a password" | sudo tee -a /etc/sudoers
echo "$(whoami) ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/init, /usr/bin/systemctl, /usr/sbin/pm-suspend, /usr/bin/awk, /usr/sbin/grub-reboot, /usr/sbin/grub2-reboot" | sudo tee -a /etc/sudoers

# Firewall Configuration
if command -v ufw &> /dev/null; then
    echo "Configuring firewall..."
    sudo ufw allow 22
else
    echo "UFW not found. Please configure the firewall manually."
fi

echo "You can now add your computer to HomeAssistant."
