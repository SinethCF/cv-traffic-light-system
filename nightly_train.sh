#!/bin/bash
# Navigate to the project root
cd /home/user/en-6

echo "[$(date)] Initiating nightly AI retraining..."

# 1. Safely kill the running Python processes to free up RAM and the camera bus
pkill -f app.py
pkill -f data_logger.py
sleep 2 

# 2. Train the new model using the training script (Virtual environment should be activated)
echo "Training new XGBoost model..."
.venv/bin/python train_model.py

# 3. Reboot the Raspberry Pi to clear cache and restart services cleanly
echo "[$(date)] Training complete. Rebooting the system..."
sudo reboot