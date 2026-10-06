# 🚦 Smart Intersection Monitor

### AI-Powered Adaptive Traffic Signal Control for Four-Way Intersections

A computer-vision-based traffic management system that uses **YOLO object detection with NCNN acceleration** to monitor traffic load across a four-way intersection and dynamically determine which predefined signal configuration should receive priority.

Designed with **edge deployment in mind**, the system can run on hardware such as the **Raspberry Pi 4**, while providing a real-time web dashboard for monitoring all four approaches.

> **Computer Vision · Edge AI · Traffic Optimization · Python · OpenCV · YOLO · NCNN · Flask**

---

## ✨ Overview

Traditional traffic lights typically operate using fixed timing cycles, regardless of how much traffic is waiting at each direction.

This project takes a different approach.

The system continuously analyzes **four video feeds**, estimates the traffic load in each monitored lane, tracks how long traffic has been waiting, and uses that information to dynamically determine:

- 🟢 Which predefined signal configuration should receive the next green phase
- ⏱️ How long the green phase should remain active
- 🚗 How heavily each lane is loaded
- ⚠️ Which lanes have reached the configured saturation threshold
- 🔄 Which configuration should follow the current one

The result is an **adaptive traffic-control simulation driven by computer-vision estimates**.

---

## 🚗 Vehicle Detection

The system uses a lightweight **YOLO26n model converted to NCNN** for efficient inference.

The detector currently considers:

| Vehicle | Relative Space Weight |
| --- | ---: |
| 🚲 Bicycle | 0.5 |
| 🚗 Car | 1.0 |
| 🏍️ Motorcycle | 0.5 |
| 🚌 Bus | 3.0 |
| 🚛 Truck | 3.0 |

Instead of simply counting every vehicle as `1`, the system uses these weights to estimate the **equivalent road-space load** represented by detected traffic.

This provides the controller with a weighted traffic-load estimate rather than a simple vehicle count.

---

## 🛣️ Lane Monitoring

Each camera represents one approach to the intersection:

```text
             NORTH
               │
          ┌────┴────┐
          │ N1  N2  │
          │         │
 WEST ────┤         ├──── EAST
          │         │
          │ S1  S2  │
          └────┬────┘
               │
             SOUTH
```

Each approach contains **two monitored lanes**, resulting in:

```text
North_1   North_2
East_1    East_2
South_1   South_2
West_1    West_2
```

Vehicle detections are assigned to lanes using predefined polygonal regions of interest.

---

## 🚦 Adaptive Traffic Controller

The traffic controller contains **six configured signal combinations**:

| Configuration | Green Movements |
| --- | --- |
| `C1` | North 2 + South 2 |
| `C2` | East 2 + West 2 |
| `C3` | North 1 + North 2 |
| `C4` | South 1 + South 2 |
| `C5` | West 1 + West 2 |
| `C6` | East 1 + East 2 |

These combinations are treated as collision-free within the simulation's configured intersection model. They are not a complete real-world signal plan and should be validated before deployment with physical traffic signals.

The controller maintains a state machine containing:

- Current active configuration
- Next locked configuration
- Remaining green-phase time
- Waiting time for each lane
- Lane saturation state
- Traffic priority scores

---

## ⏱️ Dynamic Green-Time Allocation

Green-phase duration is not fixed.

The controller calculates the required duration based on the traffic load currently assigned to the active configuration.

The calculated duration is constrained between:

```text
Minimum green time : 15 seconds
Maximum green time : 90 seconds
```

The controller uses traffic load and the proportion of traffic belonging to the active configuration to determine the final duration.

This allows heavily loaded approaches to receive more time while preventing excessively long green phases.

---

## 🧮 Priority-Based Scheduling

When deciding which configuration should receive the next green phase, the controller considers both:

### Traffic load

More weighted traffic waiting → higher priority.

### Waiting time

Traffic that has been waiting longer gradually gains priority.

---

## ⚠️ Lane Saturation & Extrapolation

A particularly important part of the controller is its handling of **camera-view saturation**.

The configured estimated capacity of a lane is:

```text
16 car-equivalent units
```

When a lane reaches this threshold, the system marks it as saturated and records its estimated filling rate.

Instead of assuming that the visible load will remain exactly at the camera's maximum observed level, the controller can extrapolate the effective traffic load using:

```text
estimated traffic = fill rate × waiting time
```

This is an estimate of traffic that may be accumulating **outside the visible camera region**; it is not a direct measurement of hidden vehicles.

If the observed traffic later falls below the saturation threshold, the extrapolation state is cancelled.

---

## 🖥️ Real-Time Dashboard

The Flask web application provides a live **2 × 2 camera grid**:

```text
┌─────────────────┬─────────────────┐
│      NORTH      │       EAST      │
│   PROCESSING    │      LIVE       │
├─────────────────┼─────────────────┤
│      SOUTH      │       WEST      │
│      LIVE       │      LIVE       │
└─────────────────┴─────────────────┘
```

The currently processed camera is highlighted while the other three feeds remain visible.

The dashboard overlays:

- Vehicle detections
- Vehicle class labels
- Lane boundaries
- Lane traffic load
- Saturation warnings
- Camera direction
- Processing status

---

## 🌐 Web API

The system also exposes the current traffic state through:

```text
GET /api/counts
```

This makes the traffic-control state available separately from the main video stream.

---

# 🛠️ Technology Stack

| Technology | Purpose |
| --- | --- |
| **Python** | Core application |
| **YOLO26n** | Vehicle detection model |
| **NCNN** | Lightweight neural-network inference runtime |
| **OpenCV** | Video processing and image manipulation |
| **NumPy** | Numerical operations and lane masks |
| **cvzone** | Detection visualization |
| **Flask** | Web server and dashboard |
| **Multithreading** | Background video-stream handling |

Dependencies are defined in [`requirements.txt`](requirements.txt).

---

# 📁 Project Structure

```text
cv-traffic-light-system/
│
├── 📁 templates/
│   ├── index.html
│   └── data.html
│
├── 📁 yolo26n_ncnn_model/
│   └── ... NCNN model files
│
├── 📄 app.py
│   └── Main computer-vision pipeline
│
├── 📄 traffic_controller.py
│   └── Adaptive traffic-control logic
│
├── 📄 requirements.txt
│   └── Python dependencies
│
├── 🖼️ mask.jpeg
│   └── Camera/background processing mask
│
├── 🤖 yolo26n.pt
│   └── YOLO model file
│
└── 📄 README.md
```

The repository includes both the NCNN model directory and the `.pt` model file shown above; the runtime path used by the application should match the configured model format.

---

# 🚀 Getting Started

## 1. Clone the repository

```bash
git clone https://github.com/SinethCF/cv-traffic-light-system.git
cd cv-traffic-light-system
```

## 2. Create a virtual environment

Linux / Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🎥 4. Add the Traffic Videos

The large `.mp4` files are intentionally **not included in the repository**.

Download the sample traffic footage:

[Busy Mumbai Road Traffic (Pexels)](https://www.pexels.com/video/busy-mumbai-road-traffic-scene-on-sunny-day-30608914/)

Then place the video in the project root and create four copies:

```text
traffic1.mp4
traffic2.mp4
traffic3.mp4
traffic4.mp4
```

The four files simulate the four camera feeds:

```text
traffic1.mp4 → NORTH
traffic2.mp4 → EAST
traffic3.mp4 → SOUTH
traffic4.mp4 → WEST
```

> **Note:** The four files can initially contain the same footage. They represent the four camera positions in the simulation and do not provide independent real-world views.

The NCNN model and `mask.jpeg` are included in the repository.

---

# ▶️ 5. Start the Application

Run:

```bash
python3 app.py
```
---

# 🌍 6. Open the Dashboard

### Local computer

Open:

```text
http://localhost:8080
```

### Raspberry Pi

Find the Raspberry Pi's IP address and open:

```text
http://<YOUR_PI_IP_ADDRESS>:8080
```

---

# 🍓 Raspberry Pi Deployment

The project was designed with **edge computing** in mind.

The use of a lightweight NCNN model is intended to make computer-vision inference more practical on CPU-oriented hardware such as the **Raspberry Pi 4**. Actual throughput and latency depend on the model, input resolution, number of feeds, and system configuration.

This architecture keeps the computer-vision processing at the edge instead of requiring a remote GPU server.

---

# 🔬 Technical Highlights

### ⚡ Lightweight inference

The YOLO model is deployed through **NCNN**, targeting efficient inference on CPU-based edge hardware.

### 🧵 Background video processing

Camera streams are continuously updated in background threads so that the main processing loop does not need to repeatedly block while reading video frames.

### 🎯 Region-based lane detection

Vehicles are classified into lanes using polygonal regions of interest and the center point of each detected bounding box.

### 🚗 Vehicle-space weighting

Different vehicle types contribute different amounts to the calculated traffic load.

### 🧠 Adaptive signal scheduling

The controller combines:

```text
Traffic Load
     +
Waiting Time
     +
Lane Saturation
     ↓
Priority Score
     ↓
Next Signal Configuration
```

### 🔄 Continuous state machine

The controller continuously maintains and updates the current signal configuration and the next planned configuration.

---

# 📊 Current System Parameters

| Parameter | Value |
| --- | ---: |
| Camera feeds | 4 |
| Monitored lanes | 8 |
| Signal configurations | 6 |
| Minimum green time | 15 s |
| Maximum green time | 90 s |
| Lane capacity threshold | 16 car-equivalent units |
| Frame resolution | 640 × 640 |
| Web server port | 8080 |

The frame rate is a target rather than a guaranteed performance level and depends on hardware, model inference time, video decoding, and the number of feeds processed.

---

# 📚 Project Goals

This project explores the combination of:

**Computer Vision + Edge AI + Embedded Systems + Traffic Engineering**

The long-term goal is to investigate whether lightweight AI systems can support traffic-control decisions dynamically using information obtained directly from an intersection.

---

## ⭐ If you find this project interesting

Feel free to ⭐ star the repository, explore the implementation, or build upon the idea.