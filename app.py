from flask import Flask, Response, render_template, jsonify
from ultralytics import YOLO
import cv2
import numpy as np
import cvzone
import threading
import time
from traffic_controller import TrafficController
import joblib
import pandas as pd
import datetime

# The main application that serves the web interface and handles the video feed using Flask.
app = Flask(__name__)

# The two models are loaded at the start of the application to avoid reloading them for every request.
model = YOLO('yolo26n_ncnn_model', task='detect')
fallback_model = joblib.load('./data/trained_model.pkl')

# Initialize the state machine globally so the API route can read it
controller = TrafficController()
system_state = {"active_config": "C1", "locked_next": "C2", "countdown": 0, "active_cam_label": "NORTH"}
cam_health_status = {"NORTH": True, "EAST": True, "SOUTH": True, "WEST": True}

frame_w, frame_h = 640, 640
dimensions = (frame_w, frame_h)

# --- REAL-TIME CAMERA SIMULATOR ---
class LiveStreamSimulator:
    def __init__(self, src):
        self.cap = cv2.VideoCapture(src)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        threading.Thread(target=self.update, args=(), daemon=True).start()

    def update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) 
                continue
            self.ret, self.frame = ret, frame
            time.sleep(1/30.0)

    def read(self):
        return self.ret, self.frame.copy() if self.frame is not None else None

video_sources = ['traffic1.mp4', 'traffic2.mp4', 'traffic3.mp4', 'traffic4.mp4']
streams = [LiveStreamSimulator(src) for src in video_sources]

lane1_area = np.array([[int(0.4 * frame_w), int(0.58 * frame_h)], [int(0.58 * frame_w), int(0.58 * frame_h)], [int(0.50 * frame_w), int(0.98 * frame_h)], [int(0.1 * frame_w), int(0.98 * frame_h)]], np.int32)
lane2_area = np.array([[int(0.58 * frame_w), int(0.58 * frame_h)], [int(0.75 * frame_w), int(0.58 * frame_h)], [int(0.87 * frame_w), int(0.98 * frame_h)], [int(0.50 * frame_w), int(0.98 * frame_h)]], np.int32)

lane1_mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
lane2_mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
cv2.fillPoly(lane1_mask, [lane1_area], 255)
cv2.fillPoly(lane2_mask, [lane2_area], 255)

bg_mask = cv2.imread("mask.jpeg")
if bg_mask is not None:
    bg_mask = cv2.resize(bg_mask, dimensions, interpolation=cv2.INTER_AREA)

target_classes = [1, 2, 3, 5, 7]

# Cardinal directions mapping for the 4 cameras
directions = ["NORTH", "EAST", "SOUTH", "WEST"]

# --- VEHICLE SPACE WEIGHTS (PCE) & CAPACITY ---
VEHICLE_WEIGHTS = {
    1: 0.5,  # Bicycle takes up half a car space
    2: 1.0,  # Car is the standard baseline
    3: 0.5,  # Motorcycle
    5: 3.0,  # Bus takes up 3 car spaces
    7: 3.0   # Truck takes up 3 car spaces
}

# Memory bank to store the 8 lane variables continuously 
intersection_counts = {
    "North_1": 0, "North_2": 0,
    "East_1": 0,  "East_2": 0,
    "South_1": 0, "South_2": 0,
    "West_1": 0,  "West_2": 0
}

def generate_frames():
    active_cam_index = 0
    frames_on_current_cam = 0
    MAX_FRAMES_PER_CAM = 10  

    # Variables to track the highest count during the frame burst (MAX_FRAMES_PER_CAM) for each lane
    burst_max_lane1 = 0.0
    burst_max_lane2 = 0.0

    # The main loop that continuously processes frames from the cameras
    while True:
        # Reset the burst max counters at the start of each new camera cycle
        if frames_on_current_cam == 0:
            burst_max_lane1 = 0.0
            burst_max_lane2 = 0.0

        current_frames = []
        camera_health = []  # Tracks cameras that are online or offline
        for stream in streams:
            ret, frame = stream.read()
            if frame is not None:
                current_frames.append(cv2.resize(frame, dimensions, interpolation=cv2.INTER_AREA))
                camera_health.append(True)
            else:
                current_frames.append(np.zeros((frame_h, frame_w, 3), dtype=np.uint8))
                camera_health.append(False)

        # Update the global health dictionary for the API
        global cam_health_status
        for i, health in enumerate(camera_health):
            cam_health_status[directions[i]] = health

        active_img = current_frames[active_cam_index]
        is_active_cam_healthy = camera_health[active_cam_index]

        # Update the master variables based on which camera is currently active
        current_direction = directions[active_cam_index]
        dir_formatted = current_direction.capitalize()

        # The HYBRID Detection Logic: Use YOLO for detection if the camera is healthy, otherwise fallback to the trained model.
        if is_active_cam_healthy:
            # Use YOLO for detection
            img_input = cv2.bitwise_and(active_img, bg_mask) if bg_mask is not None else active_img
            results = model(img_input, stream=True, classes=target_classes, verbose=False)
        
            lane1_count = 0
            lane2_count = 0
        
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    if conf >= 0.2:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        w, h = x2 - x1, y2 - y1
                        cls = int(box.cls[0])
                        name = model.names[cls]
                        cx, cy = x1 + w // 2, y1 + h // 2

                        if 0 <= cy < frame_h and 0 <= cx < frame_w:
                            # Grab the weight for this specific vehicle type (default to 1.0)
                            weight = VEHICLE_WEIGHTS.get(cls, 1.0)

                            if lane1_mask[cy, cx] == 255:
                                lane1_count += weight
                                cvzone.cornerRect(active_img, (x1, y1, w, h), colorC=(0, 255, 0), t=1)
                                cvzone.putTextRect(active_img, f"{name}", (x1, max(35, y1 - 10)), scale=1, thickness=1, colorR=(0, 200, 0))

                            elif lane2_mask[cy, cx] == 255:
                                lane2_count += weight
                                cvzone.cornerRect(active_img, (x1, y1, w, h), colorC=(255, 0, 0), t=1)
                                cvzone.putTextRect(active_img, f"{name}", (x1, max(35, y1 - 10)), scale=1, thickness=1, colorR=(200, 0, 0))

            # Update the burst max values if the current counts are higher
            burst_max_lane1 = max(burst_max_lane1, lane1_count)
            burst_max_lane2 = max(burst_max_lane2, lane2_count)

            cv2.polylines(active_img, [lane1_area], True, (0, 255, 0), 1)
            cv2.polylines(active_img, [lane2_area], True, (255, 0, 0), 1)

            # Keep the standard lane text rendering (formatted to 1 decimal place for neatness)
            cvzone.putTextRect(active_img, f"Lane 1: {burst_max_lane1:.1f}", (20, 50), scale=2, thickness=2, colorR=(0, 200, 0))
            cvzone.putTextRect(active_img, f"Lane 2: {burst_max_lane2:.1f}", (20, 100), scale=2, thickness=2, colorR=(200, 0, 0))

        else:
            # Fallback to the trained model if the camera is offline
            now = datetime.datetime.now()
            minute_of_day = now.hour * 60 + now.minute
            day_of_week = now.weekday()
            is_weekend = 1 if day_of_week >= 5 else 0

            # Recreate the exact DataFrame structure
            X_live = pd.DataFrame([{
                'minute_of_day': minute_of_day,
                'day_of_week_0': 1 if day_of_week == 0 else 0,
                'day_of_week_1': 1 if day_of_week == 1 else 0,
                'day_of_week_2': 1 if day_of_week == 2 else 0,
                'day_of_week_3': 1 if day_of_week == 3 else 0,
                'day_of_week_4': 1 if day_of_week == 4 else 0,
                'day_of_week_5': 1 if day_of_week == 5 else 0,
                'day_of_week_6': 1 if day_of_week == 6 else 0,
                'is_weekend': is_weekend
            }])

            # Make predictions using the trained model
            y_pred = fallback_model.predict(X_live)[0].astype(float)  # Ensure the predictions are float for consistency

            # Update the burst max values based on the model's predictions
            # Filter the predictions to only override the lanes for the failed camera
            # (Matches y = df[['North_1', 'North_2', 'South_1', 'South_2', 'East_1', 'East_2', 'West_1', 'West_2']])
            if current_direction == "NORTH":
                burst_max_lane1, burst_max_lane2 = y_pred[0], y_pred[1]
            elif current_direction == "SOUTH":
                burst_max_lane1, burst_max_lane2 = y_pred[2], y_pred[3]
            elif current_direction == "EAST":
                burst_max_lane1, burst_max_lane2 = y_pred[4], y_pred[5]
            elif current_direction == "WEST":
                burst_max_lane1, burst_max_lane2 = y_pred[6], y_pred[7]

            # Draw Fallback Indicators on the missing frame
            cvzone.putTextRect(active_img, "HARDWARE FAILURE", (150, 260), scale=2, thickness=2, colorR=(0, 0, 255))
            cvzone.putTextRect(active_img, "ML FALLBACK", (200, 320), scale=2, thickness=2, colorR=(0, 140, 255))
            cvzone.putTextRect(active_img, f"Lane 1: {burst_max_lane1:.1f}", (20, 50), scale=2, thickness=2, colorR=(0, 140, 255))
            cvzone.putTextRect(active_img, f"Lane 2: {burst_max_lane2:.1f}", (20, 100), scale=2, thickness=2, colorR=(0, 140, 255))


        # Update the intersection_counts dictionary based on the active camera's direction with the burst max values
        if current_direction == "NORTH":
            intersection_counts["North_1"] = burst_max_lane1
            intersection_counts["North_2"] = burst_max_lane2
        elif current_direction == "EAST":
            intersection_counts["East_1"] = burst_max_lane1
            intersection_counts["East_2"] = burst_max_lane2
        elif current_direction == "SOUTH":
            intersection_counts["South_1"] = burst_max_lane1
            intersection_counts["South_2"] = burst_max_lane2
        elif current_direction == "WEST":
            intersection_counts["West_1"] = burst_max_lane1
            intersection_counts["West_2"] = burst_max_lane2

       # Pass the latest counts to the brain to get the updated system state
        global system_state, active_cam_label
        system_state = controller.update(intersection_counts)
        active_cam_label = current_direction

        # --- Visual Saturation Alerts ---
        # The display just reads the status and draws the text. The math is hidden.
        if system_state.get("saturation_status", {}).get(f"{dir_formatted}_1", False):
            cvzone.putTextRect(active_img, "L1 SATURATED", (20, 150), scale=2, thickness=2, colorR=(0, 0, 255))
        if system_state.get("saturation_status", {}).get(f"{dir_formatted}_2", False):
            cvzone.putTextRect(active_img, "L2 SATURATED", (20, 200), scale=2, thickness=2, colorR=(0, 0, 255))
        
        # --- 2x2 GRID ASSEMBLY ---
        grid_frames = []
        for i, frame in enumerate(current_frames):
            small_frame = cv2.resize(frame, (320, 320))
            
            # Label cameras dynamically as NORTH, EAST, SOUTH, WEST
            dir_label = directions[i]
            
            if i == active_cam_index:
                # Active camera is currently being processed, so we highlight it
                if camera_health[i]:
                    cv2.rectangle(small_frame, (0, 0), (320, 320), (0, 0, 255), 6)
                    cvzone.putTextRect(small_frame, f"{dir_label} (PROCESSING)", (135, 25), scale=0.75, thickness=1, colorR=(0, 0, 255))
                else:
                    cv2.rectangle(small_frame, (0, 0), (320, 320), (0, 140, 255), 6)
                    cvzone.putTextRect(small_frame, f"{dir_label} (ML PREDICTING)", (135, 25), scale=0.75, thickness=1, colorR=(0, 140, 255))
            else:
                # Inactive cameras are just displayed normally, but we indicate if they are offline
                if camera_health[i]:
                    cvzone.putTextRect(small_frame, f"{dir_label} (LIVE)", (205, 25), scale=0.75, thickness=1, colorR=(100, 100, 100))
                else:
                    cvzone.putTextRect(small_frame, f"{dir_label} (OFFLINE)", (205, 25), scale=0.75, thickness=1, colorR=(0, 0, 255))

            grid_frames.append(small_frame)
            
        top_row = np.hstack((grid_frames[0], grid_frames[1]))
        bottom_row = np.hstack((grid_frames[2], grid_frames[3]))
        final_grid = np.vstack((top_row, bottom_row))

        # Encode the final grid as a JPEG image
        ret, buffer = cv2.imencode('.jpg', final_grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        # --- SWITCHER LOGIC ---
        frames_on_current_cam += 1
        if frames_on_current_cam >= MAX_FRAMES_PER_CAM:
            active_cam_index = (active_cam_index + 1) % 4
            frames_on_current_cam = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- ROUTE 1: Serves the new sleek HTML grid page ---
@app.route('/data')
def data_dashboard():
    return render_template('data.html')

# --- ROUTE 2: The hidden API that serves the dictionary as raw JSON ---
@app.route('/api/counts')
def api_counts():
    # We now send both the counts and the state machine data over the API
    return jsonify({
        "counts": intersection_counts,
        "state": system_state,
        "active_cam": active_cam_label,
        "cam_health": cam_health_status
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)