import pandas as pd
import numpy as np

def generate_synthetic_traffic(days=365):
    records = []
    
    # Traffic modifiers for directional commuting
    # e.g., North/South is the main highway, East/West are side streets
    lane_multipliers = {
        "North_1": 1.2, "North_2": 1.1,
        "South_1": 1.2, "South_2": 1.1,
        "East_1": 0.7,  "East_2": 0.6,
        "West_1": 0.8,  "West_2": 0.7
    }

    for day in range(days):
        day_of_week = day % 7
        is_weekend = 1 if day_of_week >= 5 else 0

        # Sample every 5 minutes to keep file size reasonable
        for minute in range(0, 1440, 5): 
            hour = minute / 60.0
            
            # Base traffic load calculation using Gaussian curves
            if not is_weekend:
                # Weekday: Morning Rush (8:00 AM) and Evening Rush (5:30 PM)
                morning_rush = 15.0 * np.exp(-0.5 * ((hour - 8.0) / 1.2)**2)
                evening_rush = 16.0 * np.exp(-0.5 * ((hour - 17.5) / 1.5)**2)
                midday_lull = 5.0
            else:
                # Weekend: Single broad peak around 1:00 PM
                morning_rush = 0.0
                evening_rush = 9.0 * np.exp(-0.5 * ((hour - 13.0) / 3.0)**2)
                midday_lull = 3.0
            
            # Combine curves and add random system noise
            base_traffic = midday_lull + morning_rush + evening_rush
            
            row = {
                "minute_of_day": minute,
                "day_of_week": day_of_week,
                "is_weekend": is_weekend
            }
            
            # Calculate individual lane counts
            for lane, multiplier in lane_multipliers.items():
                # Apply directional weight and random noise
                raw_count = base_traffic * multiplier + np.random.normal(0, 2.0)
                
                # Ensure counts are positive and cap at physical camera limit (16.0)
                final_count = np.clip(raw_count, 0.0, 16.0)
                
                # Round to nearest 0.5 to mimic PCE weights (Motorcycle = 0.5, Car = 1.0)
                row[lane] = round(final_count * 2) / 2
                
            records.append(row)
            
    df = pd.DataFrame(records)
    df.to_csv("historical_traffic_data.csv", index=False)
    print(f"Dataset generated with {len(df)} rows. Saved as 'historical_traffic_data.csv'")

if __name__ == "__main__":
    np.random.seed(42) # For reproducible results
    generate_synthetic_traffic(365)