# KrshiBandhu (कृषिबंधु) 🌾🐅

AI-powered farm animal deterrent web dashboard designed for opium and high-value crop farms vulnerable to wildlife raids. KrshiBandhu detects crop-raiding animals using open-vocabulary computer vision (**YOLO-World** on CPU), and automatically plays randomized predator sounds to scare them away (e.g. Tiger roar for deer, Nilgai, and wild boars; Hawk/Eagle cry for parrots).

---

## 🌟 Universal Deployment (Works on All Devices)

KrshiBandhu is designed to run seamlessly everywhere:
- **📱 Smart Phones & Tablets (iPhone, Android, iPad):** Open the web dashboard in Safari/Chrome. Switch source to **"This Device Camera"** to use your phone's rear or front camera directly in the field, with predator scare sounds blasting through your phone's loudspeakers!
- **💻 Farm PC / Laptop:** Connect any USB webcam (e.g. Lenovo, Logitech) or night-vision camera and external horn speakers.
- **🍓 Raspberry Pi & Linux:** Lightweight CPU inference and multi-platform Docker container.
- **☁️ Cloud Hosting:** Deploy with 1 click to Docker, Render, Railway, Hugging Face Spaces, or any Cloud VM.

---

## Key Features

- **Species Detection:** Nilgai / Blue bull, Wild boar, Deer / Blackbuck, Monkeys, Parrots / Birds, Stray cattle, Dogs / Jackals.
- **Flexible Safety:** By default, plays scare sounds immediately upon spotting crop raiders even if humans are visible, with an optional safety veto switch in Settings.
- **Predator Audio Rotation:** Avoids habituation by randomly rotating between different predator audio files (Tiger roar, Leopard growl, Hunting dog pack, Eagle screech).
- **Web Dashboard:**
  - **Live Tab:** Real-time stream with detection bounding boxes, confidence tags, camera switcher, and one-click manual scare buttons.
  - **Events Tab:** Log of animal intrusions with timestamp, thumbnail snapshot (click to enlarge), confidence, and sound triggered.
  - **Statistics Tab:** Visual charts (Chart.js) showing visits by animal, 24h/7d timeline, and hourly raid patterns (identifies peak nighttime raid hours).
  - **Settings Tab:** Camera scanner & selector, detection threshold sliders (confidence, hits required, voting window, cooldown), volume control, custom MP3/WAV/FLAC upload, animal-to-predator sound mapping matrix, and snapshot retention.
- **Bilingual Interface:** Instant English ⇄ हिन्दी (Hindi) language switcher.
- **Instant Phone Alerts:** Optional Telegram Bot notifications with snapshot photos sent directly to the farmer's mobile phone.

---

## How to Run & Deploy (शुरुआत कैसे करें)

### Option 1: Windows (1-Click)
Double-click `start_krshibandhu.bat` in this folder, or run:
```powershell
cd KrshiBandhu
.venv\Scripts\python.exe run.py
```
Open `http://localhost:8000` in your browser.

---

### Option 2: Linux / macOS / Raspberry Pi
Make `start.sh` executable and run it:
```bash
chmod +x start.sh
./start.sh
```
It automatically sets up the Python virtual environment, installs CPU PyTorch, and starts the server on port 8000.

---

### Option 3: Docker & Docker Compose
To run in a container on any system:
```bash
docker compose up -d
```
Access the dashboard at `http://localhost:8000`.

---

### Option 4: Cloud Deployment (Render / Railway / Hugging Face Spaces)
1. **Repository:** Push your fork of this repository to GitHub.
2. **Render / Railway:**
   - Create a new **Web Service** connected to your GitHub repository.
   - Environment: `Python` (or `Docker`).
   - Build Command:
     ```bash
     pip install --upgrade pip && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
     ```
   - Start Command:
     ```bash
     python run.py --host 0.0.0.0
     ```
3. **Open from any Phone or Laptop:**
   - Visit your cloud URL (e.g. `https://krshibandhu.onrender.com`).
   - Select **"📱 This Device Camera"** on the Live tab.
   - Point your phone camera at the crops — KrshiBandhu analyzes the video in real-time and sounds the predator alarm on your phone!

---

## Project Structure

```
KrshiBandhu/
├── app/
│   ├── main.py              # FastAPI backend, REST endpoints, MJPEG, WebSockets & feed_frame
│   ├── engine.py            # Main pipeline (Camera -> Detector -> Trigger -> Outputs)
│   ├── detector.py          # YOLO-World open-vocabulary model
│   ├── trigger.py           # Sliding window voting filter, cooldown & person veto
│   ├── camera.py            # Cross-platform camera capture (Windows, Linux, macOS)
│   ├── sound.py             # Pygame mixer sound library & audio playback
│   ├── storage.py           # SQLite database for intrusion events & snapshot management
│   ├── notifier.py          # Telegram bot photo notifier
│   └── config.py            # Settings persistence (settings.json)
├── sounds/                  # Curated predator deterrent sounds (.wav, .mp3, .flac)
│   ├── tiger/
│   ├── leopard/
│   ├── dogs/
│   ├── hawk/
│   ├── eagle/
│   └── human/
├── static/                  # Responsive web dashboard
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js            # Dashboard logic, WebSockets & browser camera streaming
│   ├── js/i18n.js           # English & Hindi translations
│   ├── img/logo.svg
│   └── vendor/chart.umd.min.js
├── tests/                   # Automated unit & integration tests (30 tests)
│   ├── test_trigger.py
│   ├── test_config.py
│   ├── test_storage.py
│   ├── test_api.py
│   └── smoke_detector.py
├── Dockerfile               # Multi-platform container configuration
├── docker-compose.yml       # Docker compose orchestration
├── run.py                   # CLI & browser auto-launcher (reads PORT & HOST env)
├── start_krshibandhu.bat    # Windows 1-click startup script
├── start.sh                 # Linux / macOS / Raspberry Pi startup script
└── requirements.txt
```

---

## Testing (जाँच)

Run all 30 automated unit and integration tests:
```powershell
.venv\Scripts\python.exe -m pytest -q
```
All tests cover detection pipelines, frame feeding from mobile/browser devices, trigger voting, sound rotation, settings persistence, snapshot archival, and WebSocket streaming.

---

## Farm Deployment Tips (खेत में उपयोग के सुझाव)

1. **Camera Placement:** Mount your USB webcam, smartphone, or night-vision camera under a covered shelter facing the crop entry point.
2. **Loudspeakers:** Connect an external powered speaker or horn amplifier to your PC's 3.5mm audio jack or Bluetooth for high volume across the field.
3. **Night Raids:** Enable the *Low-light boost* switch in the Settings tab, or plug in an IR USB camera.
4. **Telegram Alerts:** To receive intrusion photos on your phone, open Telegram, search `@BotFather`, create a bot to get your API Token, and paste it along with your Chat ID in the Settings tab.
