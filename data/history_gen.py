import pandas as pd
import numpy as np

print("Initializing high-speed realistic traffic simulation...")

# 100 days * 1440 minutes per day = 144,000 rows of data
num_days = 100
minutes_per_day = 1440
total_rows = num_days * minutes_per_day

# 1. Create continuous time features
days = np.repeat(np.arange(num_days), minutes_per_day)
minute_of_day = np.tile(np.arange(minutes_per_day), num_days)
day_of_week = days % 7
is_weekend = (day_of_week >= 5).astype(int)

# 2. Build the Kinematic Traffic Waves (Gaussian Curves)
# Morning rush hour peaks around 8:00 AM (480 mins)
morning_rush = 1.5 * np.exp(-0.5 * ((minute_of_day - 480) / 60)**2)

# Evening rush hour peaks around 5:30 PM (1050 mins)
evening_rush = 1.8 * np.exp(-0.5 * ((minute_of_day - 1050) / 90)**2)

# General daytime baseline traffic (Sine wave)
midday_base = 0.5 * np.sin(np.pi * minute_of_day / 1440)

# Weekend traffic is flatter and peaks mid-day around 1:00 PM (780 mins)
weekend_peak = 1.2 * np.exp(-0.5 * ((minute_of_day - 780) / 200)**2) + 0.3

# 3. Merge profiles logically based on the day type
weekday_profile = morning_rush + evening_rush + midday_base + 0.2
weekend_profile = weekend_peak

# Apply the correct profile to the specific row
master_vol = np.where(is_weekend == 1, weekend_profile, weekday_profile)

# 4. Route Weighting (Simulating major vs minor roads)
# North/South arteries handle more volume than East/West cross-streets
ns_vol = master_vol * 6.0
ew_vol = master_vol * 4.0

# 5. Generate Poisson noise (multiplied and divided by 2 to create 0.5 increments) and clip to camera capacity (18)
data = {
    'minute_of_day': minute_of_day,
    'day_of_week': day_of_week,
    'is_weekend': is_weekend,
    'North_1': np.clip(np.random.poisson(ns_vol * 2) / 2.0, 0, 18),
    'North_2': np.clip(np.random.poisson(ns_vol * 1.8) / 2.0, 0, 18),
    'South_1': np.clip(np.random.poisson(ns_vol * 2) / 2.0, 0, 18),
    'South_2': np.clip(np.random.poisson(ns_vol * 1.8) / 2.0, 0, 18),
    'East_1':  np.clip(np.random.poisson(ew_vol * 2) / 2.0, 0, 18),
    'East_2':  np.clip(np.random.poisson(ew_vol * 1.6) / 2.0, 0, 18),
    'West_1':  np.clip(np.random.poisson(ew_vol * 2) / 2.0, 0, 18),
    'West_2':  np.clip(np.random.poisson(ew_vol * 1.6) / 2.0, 0, 18)
}

# 6. Compile and Export
df = pd.DataFrame(data)
df.to_csv('./data/history.csv', index=False)
print(f"Success! {len(df):,} rows of 1-minute interval data saved to ./data/history.csv")