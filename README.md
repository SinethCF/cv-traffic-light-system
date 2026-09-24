# Smart Intersection Monitor (NCNN Accelerated)

A highly optimized, multi-camera traffic monitoring dashboard designed for edge deployment on devices like the Raspberry Pi 4. This system utilizes a custom YOLO26 nano model compiled with the NCNN framework to maximize CPU inference speeds. It features instant $O(1)$ matrix coordinate lookups for lane counting and a multithreaded background architecture to dynamically cycle through 4 continuous camera feeds without dropping frames.

## 🛠️ System Setup

### 1. Clone the Repository
Pull the latest code from GitHub to your local machine or Raspberry Pi:
```bash
git clone https://github.com/SinethCF/cv-traffic-light-system.git
cd cv-traffic-light-system
```

### 2. Install Dependencies
It is highly recommended to isolate your packages using a Python virtual environment.
```bash
# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install the required libraries (including ncnn and Flask)
pip install -r requirements.txt
```

### 3. Configure Video Feeds
To keep this repository lightweight and fast, the heavy `.mp4` video files are excluded. You must download the sample footage manually to run the simulation:
1. Download the base traffic video here: [Busy Mumbai Road Traffic (Pexels)](https://www.pexels.com/video/busy-mumbai-road-traffic-scene-on-sunny-day-30608914/)
2. Place the downloaded video into the root directory of this project (in the same folder as `app.py`).
3. Make 4 separate copies of the video and rename them exactly as follows to simulate the four intersection cameras:
   * `traffic1.mp4`
   * `traffic2.mp4`
   * `traffic3.mp4`
   * `traffic4.mp4`

*(Note: The AI engine `yolo26n_ncnn_model` and the background `mask.jpeg` are already included in the repository.)*

### 4. Launch the Dashboard
Start the Flask server to fire up the NCNN inference engine and the web application.
```bash
python3 app.py
```

### 5. Access the Interface
Open your web browser to view the live 4-camera grid:
* **Local PC:** Navigate to `http://localhost:8080`
* **Raspberry Pi:** Navigate to `http://<YOUR_PI_IP_ADDRESS>:8080`
