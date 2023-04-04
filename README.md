# Easy Computer Manage

## Configure Linux-running computer to be managed by Home Assistant.
We need to allow your user to run specific sudo command without asking for password. To do this, we need to edit sudoers file. To do this, run the following command in terminal: ``visudo``

```
# Allow your user user to execute shutdown, init, systemctl, pm-suspend, awk, grub-reboot, and grub2-reboot without a password
username ALL=(ALL) NOPASSWD: /sbin/shutdown
username ALL=(ALL) NOPASSWD: /sbin/init
username ALL=(ALL) NOPASSWD: /usr/bin/systemctl
username ALL=(ALL) NOPASSWD: /usr/sbin/pm-suspend
username ALL=(ALL) NOPASSWD: /usr/bin/awk
username ALL=(ALL) NOPASSWD: /usr/sbin/grub-reboot
username ALL=(ALL) NOPASSWD: /usr/sbin/grub2-reboot
```
Be sure to replace username with your username.

## Configure Windows-running computer to be managed by Home Assistant.
First go to "Optional Features" in Windows 10, look for "OpenSSH Server" and install it.
Then open "Services", find "OpenSSH Server", open "Properties" and set the service to start "Automatically", you can also manually start the service for the first time.  

*Note : It might be necessary to allow port 22 (ssh) in the Windows firewall.*

## Configure dual-boot (Windows/Linux) computer to be managed by Home Assistant.
To configure dual-boot computer, you need to configure both Windows and Linux, for this look at the 2 sections above.  
You will need to have the same username and password on both Windows and Linux.

*Note : Be sure to enable the checkbox "Dual boot system" when adding your PC to home assistant.*

## Why not use SSH keys?
Well, simply because it would require the user to do some extra steps. Using the password, it's almost plug and play.
But maybe in the future I will add the option to use SSH keys depending on the feedback.

