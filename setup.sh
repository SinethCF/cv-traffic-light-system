#!/bin/bash

# Navigate to the actual project directory
cd /home/user/en-6

echo "Starting automated deployment for Traffic Control System..."

# Grant execution permissions to all shell scripts
echo "Setting executable permissions..."
chmod +x nightly_train.sh startup.sh setup.sh

# Safely configure Cron Jobs
echo "Configuring crontab..."

# Export current cron jobs to a temporary file (ignores error if crontab is empty)
crontab -l > temp_cron 2>/dev/null || true

# Check if the nightly train job already exists, append if it doesn't
if ! grep -q "/home/user/en-6/nightly_train.sh" temp_cron; then
    echo "0 2 * * * /home/user/en-6/nightly_train.sh >> /home/user/en-6/cron.log 2>&1" >> temp_cron
    echo "[+] Added 2:00 AM nightly training routine."
else
    echo "[-] Nightly training cron already exists. Skipping."
fi

# Check if the startup job already exists, append if it doesn't
if ! grep -q "/home/user/en-6/startup.sh" temp_cron; then
    echo "@reboot /home/user/en-6/startup.sh >> /home/user/en-6/cron.log 2>&1" >> temp_cron
    echo "[+] Added auto-startup on reboot routine."
else
    echo "[-] Auto-startup cron already exists. Skipping."
fi

# Load the updated file back into the system's cron scheduler and delete the temp file
crontab temp_cron
rm temp_cron

echo "Deployment successful! The edge-AI pipeline is fully automated."