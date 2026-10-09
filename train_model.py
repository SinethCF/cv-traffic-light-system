import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor
import joblib

# Load your traffic data CSV file
df = pd.read_csv('./data/history.csv')  

# Preprocess the data
x = df[['minute_of_day', 'day_of_week', 'is_weekend']]
y = df[['North_1', 'North_2', 'South_1', 'South_2', 'East_1', 'East_2', 'West_1', 'West_2']]

# Replacing day_of_week with one-hot encoding
x = pd.get_dummies(x, prefix="day_of_week", columns=['day_of_week'])

# Reorder the columns to ennsure 'is_weekend' is the last column
x = x[['minute_of_day'] + [col for col in x.columns if col.startswith('day_of_week_')] + ['is_weekend']]

# Split the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(x, y, train_size=0.8, random_state=42)

# Define the base XGBoost model
base_model = XGBRegressor(objective='reg:squarederror', n_estimators=60, learning_rate=0.1, random_state=42)

# Wrap the base model in MultiOutputRegressor BEFORE fitting
multi_output_model = MultiOutputRegressor(base_model)

# Fit the wrapper model on the training data
multi_output_model.fit(X_train, y_train) 

# Make multi-output predictions on the test set
y_train_pred = multi_output_model.predict(X_train)
y_test_pred = multi_output_model.predict(X_test)

# Calculate the real-world error of the model
mse_train = mean_squared_error(y_train, y_train_pred)
mse_test = mean_squared_error(y_test, y_test_pred)

# Save the trained model
joblib.dump(multi_output_model, './data/trained_model.pkl')