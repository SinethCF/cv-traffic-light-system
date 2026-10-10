#!/bin/bash
cd /home/user/en-6

echo "[$(date)] System booted. Starting traffic network..."

# Launch the live intersection using the .venv Python
nohup .venv/bin/python app.py > system.log 2>&1 &

sleep 5 

# Launch the logger using the .venv Python
nohup .venv/bin/python data_logger.py > logger.log 2>&1 &

echo "[$(date)] Startup complete."