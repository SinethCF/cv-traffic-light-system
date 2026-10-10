import time
import requests
import pandas as pd
import datetime

API_URL = "http://127.0.0.1:8080/api/counts"
CSV_PATH = "./data/history.csv"

print("Starting Traffic Data Logger Microservice...")
print(f"Polling {API_URL} every 60 seconds.")

while True:
    # Sync to the exact top of the next minute for perfectly clean data intervals
    now = datetime.datetime.now()
    sleep_time = 60 - now.second
    time.sleep(sleep_time)

    try:
        # Fetch live data from the independent Flask API
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            counts = data['counts']

            # Capture the exact time of the API read
            log_time = datetime.datetime.now()
            minute_of_day = log_time.hour * 60 + log_time.minute
            day_of_week = log_time.weekday()
            is_weekend = 1 if day_of_week >= 5 else 0

            # Format the new row exactly like your history.csv
            new_row = pd.DataFrame([{
                'minute_of_day': minute_of_day,
                'day_of_week': day_of_week,
                'is_weekend': is_weekend,
                'North_1': counts['North_1'],
                'North_2': counts['North_2'],
                'South_1': counts['South_1'],
                'South_2': counts['South_2'],
                'East_1': counts['East_1'],
                'East_2': counts['East_2'],
                'West_1': counts['West_1'],
                'West_2': counts['West_2']
            }])

            # Load the dataset, apply FIFO (First In, First Out), and save
            df = pd.read_csv(CSV_PATH)
            
            # Drop the oldest row (index 0) and append the new live data
            df = pd.concat([df.iloc[1:], new_row], ignore_index=True)
            
            # Silently overwrite the CSV file
            df.to_csv(CSV_PATH, index=False)
            
            print(f"[{log_time.strftime('%H:%M:%S')}] Logged live traffic. Dataset maintained at {len(df)} rows.")
            
        else:
            print(f"API Error: Received status {response.status_code}")
            
    except Exception as e:
        # If app.py is offline, the logger just waits patiently for the next minute
        print(f"Connection failed: Is the main app running? Retrying in 60s...")