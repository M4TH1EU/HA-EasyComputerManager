# Install OpenSSH Components
Write-Host "Installing OpenSSH Components..."

# Check if OpenSSH is installed
$opensshInstalled = Get-WindowsOptionalFeature -Online | Where-Object FeatureName -eq "OpenSSH.Client"
$opensshServerInstalled = Get-WindowsOptionalFeature -Online | Where-Object FeatureName -eq "OpenSSH.Server"

# Install OpenSSH Client and Server if not installed
if (!$opensshInstalled) {
    Write-Host "Installing OpenSSH Client..."
    Add-WindowsCapability -Online -Name OpenSSH.Client
}

if (!$opensshServerInstalled) {
    Write-Host "Installing OpenSSH Server..."
    Add-WindowsCapability -Online -Name OpenSSH.Server
}

# Start and set OpenSSH Server to Automatic
Write-Host "Configuring OpenSSH Server..."
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd

# Confirm the Firewall rule is configured. It should be created automatically by setup. Run the following to verify
if (!(Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue | Select-Object Name, Enabled)) {
    Write-Output "Firewall Rule 'OpenSSH-Server-In-TCP' does not exist, creating it..."
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
} else {
    Write-Output "Firewall rule 'OpenSSH-Server-In-TCP' has been created and exists."
}