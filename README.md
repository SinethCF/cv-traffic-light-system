# 🚦 Smart Intersection Monitor
### AI-Powered Adaptive Traffic Signal Control for Four-Way Intersections

Smart Intersection Monitor is a computer-vision-based prototype for adaptive traffic-signal scheduling at a four-way intersection. It uses a lightweight YOLO model deployed through NCNN to estimate traffic loads from four video feeds, then applies a Python traffic controller to select the next predefined signal configuration and calculate a variable green-light duration.

The repository also includes a Flask dashboard, an auxiliary machine-learning model for estimating traffic when a video source is unavailable, a traffic-data logger, and an optional Raspberry Pi hardware controller for LED traffic signals and countdown displays.

> **Project status:** This is an experimental/academic prototype. Its signal configurations, camera estimates, timing logic, and hardware fallback behavior are not certified for controlling public-road traffic.

**Technologies:** Python · YOLO26n · NCNN · OpenCV · NumPy · cvzone · Flask · scikit-learn · XGBoost · Raspberry Pi (optional)

---

## 📌 Contents

- [Overview](#-overview)
- [How it works](#-how-it-works)
- [Vehicle detection and traffic-load weights](#-vehicle-detection-and-traffic-load-weights)
- [Lane monitoring](#-lane-monitoring)
- [Adaptive traffic controller](#-adaptive-traffic-controller)
- [Dashboard and API](#-dashboard-and-api)
- [Project structure](#-project-structure)
- [Getting started](#-getting-started)
- [Optional data logging and model retraining](#-optional-data-logging-and-model-retraining)
- [Optional Raspberry Pi hardware controller](#-optional-raspberry-pi-hardware-controller)
- [Deployment scripts](#-deployment-scripts)
- [Current parameters](#-current-parameters)

---

## ✨ Overview

Conventional fixed-time traffic signals use predetermined schedules even when traffic demand changes. This project explores an adaptive alternative by estimating how much traffic is waiting in each monitored lane and using both traffic load and waiting time to schedule signal phases.

The current implementation:

- Reads four video sources representing the **north, east, south, and west** approaches.
- Detects bicycles, cars, motorcycles, buses, and trucks using the YOLO26n NCNN model.
- Assigns each detected vehicle to one of two fixed regions of interest in its video frame.
- Estimates traffic load using vehicle-space weights rather than treating every vehicle as identical.
- Tracks waiting time, lane saturation, and priority scores.
- Selects the next configuration from six predefined configurations and calculates a green duration.
- Serves a live dashboard and JSON API through Flask.
- Can optionally drive physical LEDs and countdown displays through a separate Raspberry Pi hardware-controller process.

The current video inputs are files named `traffic1.mp4` to `traffic4.mp4`; the application does not automatically discover four USB cameras. The videos are used as a simulation of the four approaches. In real-life cases, these videos can be replaced with the live video stream as necessary.

---

## ⚙️ How it works

Frames are read continuously by background stream threads. The detection loop processes the four approaches in rotation rather than running YOLO inference on all four at the same instant. Each input frame is resized to **640 × 640** before detection. Then the YOLO model detects the vehicles and their types, and assigns values to each lane of every approach. The dashboard combines the four views into a 2 × 2 grid. Using predefined rules, and other parameters, a priority score is assigned for each lane. This is then used to establish the next Green configuration in the system.

If a video source cannot provide a frame, the application marks that camera as unavailable and uses the separate trained regression model to estimate lane loads from time-and-calendar features. This is a prediction based on historical data, not a live measurement of traffic in the unavailable view.

---

## 🚗 Vehicle detection and traffic-load weights

The application loads the NCNN model from `yolo26n_ncnn_model/`:

Vehicles are assigned the following relative space weights in `app.py`:

| Vehicle class | Weight | Interpretation |
| --- | ---: | --- |
| Bicycle | 0.5 | Half of the car baseline |
| Car | 1.0 | Reference unit |
| Motorcycle | 0.5 | Half of the car baseline |
| Bus | 3.0 | Three car-equivalent units |
| Truck | 3.0 | Three car-equivalent units |

These are project-defined approximations of relative road-space usage. The resulting lane values are **weighted traffic-load estimates**, not necessarily the literal number of vehicles.

The detector currently uses a confidence threshold of `0.2` and selects the supported vehicle classes by their model class IDs. The optional `mask.jpeg` image is applied before inference when it can be loaded; it is resized to the processing resolution.

---

## 🛣️ Lane monitoring

Each video represents one approach, and each approach is divided into two monitored regions:

```text
                 NORTH
              North_1  North_2
                  │       │
       WEST ──────┤       ├────── EAST
        West_1    │       │    East_1
        West_2    │       │    East_2
                  │       │
              South_1  South_2
                 SOUTH
```

The eight lane identifiers used by the application and controller are:

- `North_1`, `North_2`
- `East_1`, `East_2`
- `South_1`, `South_2`
- `West_1`, `West_2`

The two lane regions are defined by fixed polygon coordinates in `app.py`. Their shape and placement depend on the camera view. If different footage or camera angles are used, adjust the regions of interest—and, where necessary, `mask.jpeg`—and validate that vehicles are assigned to the intended lanes.

---

## 🚦 Adaptive traffic controller

The scheduling logic is implemented in `traffic_controller.py`. It maintains the active configuration, the next locked configuration, remaining phase time, lane waiting timers, saturation state, and traffic-priority scores.

### Signal configurations

The controller defines these six green-phase configurations:

| Configuration | Lanes assigned green |
| --- | --- |
| `C1` | `North_2` + `South_2` |
| `C2` | `East_2` + `West_2` |
| `C3` | `North_1` + `North_2` |
| `C4` | `South_1` + `South_2` |
| `C5` | `West_1` + `West_2` |
| `C6` | `East_1` + `East_2` |

### Dynamic green-time allocation

The controller estimates a green duration from the effective traffic load assigned to the selected configuration and its share of the estimated load across all lanes. This allows heavily loaded approaches to receive more time while preventing excessively long green phases.

### Priority-based scheduling

The next configuration is selected using a priority score that combines:

- **Visible weighted traffic load:** configurations with more waiting traffic receive a higher score.
- **Waiting time:** waiting time is weighted quadratically, so a lane that has waited longer can gain priority even when its visible load is not the largest.

The priority calculation uses the visible lane counts. Green-time allocation can additionally use the controller's saturation estimate.

### Lane saturation and extrapolation

The configured lane-capacity threshold is currently at **16 car-equivalent units**. When a waiting lane reaches this threshold, the controller records an estimated filling rate and can extrapolate an effective load as the wait continues. This attempts to account for queues that may extend beyond the visible camera region.

Extrapolated traffic is an estimate—not a direct observation of vehicles outside the frame. The controller resets the extrapolation state when the visible count falls below the threshold or the lane becomes active.

---

## 🖥️ Dashboard and API

The Flask app runs on port **8080** and provides these endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Main dashboard with the combined four-camera video display |
| `GET /video_feed` | MJPEG stream used by the main dashboard |
| `GET /data` | Traffic-data dashboard |
| `GET /api/counts` | JSON endpoint for lane counts, controller state, camera health, and heartbeat |

The main dashboard shows the four approaches in a 2 × 2 grid. The currently processed feed is highlighted. Depending on the frame and camera state, overlays can show vehicle boxes and labels, lane regions, estimated lane loads, saturation warnings, and camera-processing status.

The JSON response contains:

- `counts` — the latest estimated load for each of the eight lanes.
- `state` — the controller's active/next configuration, phase, countdown, waiting timers, saturation status, and display timing data.
- `active_cam` — the approach currently being processed.
- `cam_health` — availability status for the four video sources.
- `heartbeat` — timestamp updated by the processing loop; the hardware controller uses it to detect loss of the main application.

The server binds to `0.0.0.0`, so it can be reachable from other devices on the same network. The API has no authentication; keep it on a trusted private network and do not expose port `8080` directly to the public internet.

---

## 📁 Project structure

```text
cv-traffic-light-system/
├── data/
│   ├── history.csv                 # Historical lane-load data
│   └── trained_model.pkl           # Trained fallback traffic-load predictor
├── templates/
│   ├── index.html                  # Main video dashboard
│   └── data.html                   # Lane-data dashboard
├── yolo26n_ncnn_model/             # NCNN model used by app.py
├── .gitignore
├── app.py                          # Video processing, detection, Flask server and API
├── data_logger.py                  # Collects periodic samples from the API
├── hardware_controller.py          # Optional Raspberry Pi LED/display controller
├── mask.jpeg                       # Optional preprocessing mask
├── nightly_train.sh                # Environment-specific scheduled retraining script
├── requirements.txt                # Core Python dependencies (not every script dependency)
├── setup.sh                        # Environment-specific cron setup script
├── startup.sh                      # Environment-specific service startup script
├── traffic_controller.py           # Adaptive phase and priority logic
├── train_model.py                  # Trains the fallback regression model
├── yolo26n.pt                      # PyTorch checkpoint; not loaded by the current app runtime
└── README.md
```

The four `.mp4` traffic videos are **not tracked in the repository** because video files are excluded by `.gitignore`. The `data/` directory contains the historical dataset and the trained regression-model artifact expected by the app.

---

## 🚀 Getting started

### 1. Clone the repository

```bash
git clone https://github.com/SinethCF/cv-traffic-light-system.git
cd cv-traffic-light-system
```

### 2. Create and activate a virtual environment

**Linux / Raspberry Pi / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Use a recent Python 3 version compatible with the installed ML and OpenCV packages.

### 3. Install the application dependencies

Install the dependencies listed in the repository:

```bash
python -m pip install -r requirements.txt
```

The repository currently expects these files to be present:

- `yolo26n_ncnn_model/` — NCNN detection model directory.
- `data/trained_model.pkl` — trained regression model loaded at app startup.
- `data/history.csv` — historical lane-load data used for retraining.

`mask.jpeg` is used when available. If a video source is missing or cannot be opened, the application may use the historical predictor for that approach, but this should not be interpreted as a live traffic measurement.

### 4. Add the four traffic-video inputs

Download the sample footage from [Pexels — Busy Mumbai Road Traffic](https://www.pexels.com/video/busy-mumbai-road-traffic-scene-on-sunny-day-30608914/) or use suitable traffic clips of your own.

Place four video files in the **project root** with these exact names:

```text
traffic1.mp4  → NORTH
traffic2.mp4  → EAST
traffic3.mp4  → SOUTH
traffic4.mp4  → WEST
```

For a quick software demonstration, all four filenames can point to copies of the same sample clip. They will not represent four independent viewpoints in that case. For meaningful lane comparisons, use footage appropriate to each approach and adjust the lane polygons to match it.

### 5. Start the application

From the project root, with the virtual environment active:

```bash
python app.py
```

The application loads the detection model and fallback predictor, starts the video-processing loop, and launches the Flask server.

### 6. Open the dashboard

On the same computer, open:

- Main dashboard: <http://localhost:8080>
- Traffic-data dashboard: <http://localhost:8080/data>
- JSON API: <http://localhost:8080/api/counts>

To access the dashboard from another device on the same network, replace `localhost` with the host computer's IP address, for example `http://192.168.1.20:8080`. Use the actual IP assigned to your device.

Press **Ctrl+C** in the terminal to stop the foreground application.

---

## 📈 Optional data logging and model retraining

These tools are separate from the main detection and scheduling loop.

### Data logger

`data_logger.py` polls `GET /api/counts` approximately once per minute and writes the timestamp features and eight lane loads into `data/history.csv`. It maintains a rolling dataset by dropping the oldest row and appending the newest sample.

Start the main app first, then run the logger in a **second terminal** with the same virtual environment active:

```bash
python data_logger.py
```

Stop it with **Ctrl+C** when finished. Keep a backup of `data/history.csv` if you want to preserve collected samples, because each logging cycle replaces the oldest row rather than growing the file indefinitely.

### Train the fallback traffic-load predictor

`train_model.py` trains a multi-output XGBoost regression model using the historical dataset. Its inputs are time-of-day and calendar features; its outputs are the estimated lane loads. The trained model is saved to `data/trained_model.pkl` and is used by `app.py` when a video feed is unavailable.

Run it from the project root:

```bash
python train_model.py
```

This retrains the **fallback traffic-load predictor**, not the YOLO vehicle detector. Ensure `data/history.csv` contains the expected columns before training. Restart `app.py` after retraining so the newly saved model is loaded into memory.

---

## 🍓 Optional Raspberry Pi hardware controller

The project was designed with edge computing in mind.

The use of a lightweight NCNN model is intended to make computer-vision inference more practical on CPU-oriented hardware such as the Raspberry Pi 4. Actual throughput and latency depend on the model, input resolution, number of feeds, and system configuration.

This architecture keeps the computer-vision processing at the edge instead of requiring a remote GPU server.

`hardware_controller.py` is a separate process for prototype hardware. It reads the local API at `http://127.0.0.1:8080/api/counts` and uses the returned controller state to operate traffic-light LEDs and countdown displays.

The current implementation is written for a Raspberry Pi setup using:

- MCP23017 I²C I/O expanders for the red, yellow, and green LEDs.
- TM1637 four-digit seven-segment displays for countdown information.
- Raspberry Pi I²C/GPIO access and wiring matching the pin and bus configuration in `hardware_controller.py`.

This script is **not required** for running the software dashboard. Use it only on the configured Raspberry Pi with the electronics connected correctly. The core `requirements.txt` also include the hardware packages necessary for the hardware modules connected.

Start `app.py` first. In a second terminal on the Raspberry Pi, run:

```bash
python hardware_controller.py
```

Check the bus numbers, GPIO pins, I²C enablement, device addresses, and wiring in `hardware_controller.py` before running it. The code attempts to enter a blinking-yellow fallback if the application's heartbeat stops changing for about 10 seconds.

---

## 🕒 Deployment scripts (OFFICIAL METHOD)

The repository includes `setup.sh`, `startup.sh`, and `nightly_train.sh` for the deployment arrangement.

- `setup.sh` installs cron entries for startup and nightly retraining.
- `startup.sh` launches the app, data logger, and hardware controller using `.venv` directly in the background instantaneously.
- `nightly_train.sh` stops the app and logger, retrains the fallback model, and requests a system reboot.

These scripts are **environment-specific and should not be run unchanged on another machine**. Update the paths, review the commands and permissions, and confirm that scheduled reboot behavior is appropriate for your installation before enabling the cron jobs.

---

## 📊 Current parameters

| Parameter | Current setting |
| --- | ---: |
| Video sources | 4 |
| Monitored lanes | 8 (2 per approach) |
| Signal configurations | 6 |
| Input frame size | 640 × 640 |
| Main dashboard layout | 2 × 2 video grid |
| Detection confidence threshold | 0.2 |
| Minimum green duration | 15 seconds |
| Maximum green duration | 90 seconds |
| Green-to-yellow interval | 3 seconds |
| Red/yellow preparation interval | 2 seconds |
| Lane saturation threshold | 16 car-equivalent units |
| Flask port | 8080 |
| Hardware heartbeat timeout | About 10 seconds |

Values are defined in the Python source and may change as the project evolves.

---

## 🎯 Project goals

This project explores how computer vision, lightweight edge inference, adaptive scheduling, and optional embedded hardware can be combined to investigate traffic-responsive control at a four-way intersection.

Contributions, issue reports, and improvements to the model, camera calibration, control logic, documentation, and testing are welcome.

---

## ⭐ If you find this project interesting

Feel free to ⭐ star the repository, explore the implementation, or build upon the idea.