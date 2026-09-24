from flask import Flask, Response, render_template
from ultralytics import YOLO
import cv2
import numpy as np
import cvzone
import threading
import time

app = Flask(__name__)
model = YOLO('yolo26n_ncnn_model', task='detect')

frame_w, frame_h = 640, 640
dimensions = (frame_w, frame_h)

# --- 1. REAL-TIME CAMERA SIMULATOR ---
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

def generate_frames():
    active_cam_index = 0
    frames_on_current_cam = 0
    MAX_FRAMES_PER_CAM = 15  
    
    while True:
        current_frames = []
        for stream in streams:
            ret, frame = stream.read()
            if frame is not None:
                current_frames.append(cv2.resize(frame, dimensions, interpolation=cv2.INTER_AREA))
            else:
                current_frames.append(np.zeros((frame_h, frame_w, 3), dtype=np.uint8))

        active_img = current_frames[active_cam_index]
        img_input = cv2.bitwise_and(active_img, bg_mask) if bg_mask is not None else active_img
        
        results = model(img_input, stream=True, classes=target_classes, verbose=False)
        
        lane1_count = 0
        lane2_count = 0
        
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf >= 0.3:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    w, h = x2 - x1, y2 - y1
                    cls = int(box.cls[0])
                    name = model.names[cls]
                    cx, cy = x1 + w // 2, y1 + h // 2

                    if 0 <= cy < frame_h and 0 <= cx < frame_w:
                        if lane1_mask[cy, cx] == 255:
                            lane1_count += 1
                            cvzone.cornerRect(active_img, (x1, y1, w, h), colorC=(0, 255, 0), t=1)
                            cvzone.putTextRect(active_img, f"{name}", (x1, max(35, y1 - 10)), scale=1, thickness=1, colorR=(0, 200, 0))
                        elif lane2_mask[cy, cx] == 255:
                            lane2_count += 1
                            cvzone.cornerRect(active_img, (x1, y1, w, h), colorC=(255, 0, 0), t=1)
                            cvzone.putTextRect(active_img, f"{name}", (x1, max(35, y1 - 10)), scale=1, thickness=1, colorR=(200, 0, 0))

        cv2.polylines(active_img, [lane1_area], True, (0, 255, 0), 1)
        cv2.polylines(active_img, [lane2_area], True, (255, 0, 0), 1)
        
        cvzone.putTextRect(active_img, f"Lane 1: {lane1_count}", (20, 50), scale=2, thickness=2, colorR=(0, 200, 0))
        cvzone.putTextRect(active_img, f"Lane 2: {lane2_count}", (20, 100), scale=2, thickness=2, colorR=(200, 0, 0))
        
        # --- 3. 2x2 GRID ASSEMBLY ---
        grid_frames = []
        for i, frame in enumerate(current_frames):
            small_frame = cv2.resize(frame, (320, 320))
            
            if i == active_cam_index:
                cv2.rectangle(small_frame, (0, 0), (320, 320), (0, 0, 255), 6)
                # Positioned top-right and scaled down to avoid covering lane stats
                cvzone.putTextRect(small_frame, f"CAM {i+1} (PROCESSING)", (125, 25), scale=0.8, thickness=1, colorR=(0, 0, 255))
            else:
                cvzone.putTextRect(small_frame, f"CAM {i+1} (LIVE)", (215, 25), scale=0.8, thickness=1, colorR=(100, 100, 100))
                
            grid_frames.append(small_frame)
            
        top_row = np.hstack((grid_frames[0], grid_frames[1]))
        bottom_row = np.hstack((grid_frames[2], grid_frames[3]))
        final_grid = np.vstack((top_row, bottom_row))

        ret, buffer = cv2.imencode('.jpg', final_grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        # --- 4. SWITCHER LOGIC ---
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)