# KrshiBandhu (कृषिबंधु) 🌾🐅

AI-powered farm animal deterrent web dashboard designed for opium and high-value crop farms vulnerable to wildlife raids. KrshiBandhu monitors your farm through any connected USB webcam, detects crop-raiding animals using open-vocabulary computer vision (**YOLO-World** on CPU), and automatically plays randomized predator sounds through your PC speakers (e.g. Tiger roar for deer, Nilgai, and wild boars; Hawk/Eagle cry for parrots).

---

## Key Features

- **Species Detection:** Nilgai / Blue bull, Wild boar, Deer / Blackbuck, Monkeys, Parrots / Birds, Stray cattle, Dogs / Jackals.
- **Safety First (Human Protection):** Detects humans in the frame; **never** plays predator sounds while farm workers or visitors are visible.
- **Predator Audio Rotation:** Avoids habituation by randomly picking between different predator sounds (e.g. Tiger roar, Leopard growl, Hunting dog pack, Eagle screech).
- **Web Dashboard:**
  - **Live Tab:** Real-time MJPEG camera stream with detection bounding boxes, confidence tags, and one-click manual scare buttons.
  - **Events Tab:** Log of animal intrusions with timestamp, thumbnail snapshot (click to enlarge), confidence, and sound triggered.
  - **Statistics Tab:** Visual charts (Chart.js) showing visits by animal, 24h/7d timeline, and hourly raid patterns (identifies peak nighttime raid hours).
  - **Settings Tab:** Camera scanner & selector, detection threshold sliders (confidence, hits required, voting window, cooldown), volume control, custom MP3/WAV/FLAC upload, animal-to-predator sound mapping matrix, and snapshot retention.
- **Bilingual Interface:** Instant English ⇄ हिन्दी (Hindi) language switcher.
- **Instant Phone Alerts:** Optional Telegram Bot notifications with snapshot photos sent directly to the farmer's mobile phone.
- **Offline Capable:** Runs entirely locally on your Windows PC (CPU). No internet needed for farm operations; only Telegram alerts require connectivity.

---

## Quick Start (शुरुआत कैसे करें)

### 1. Launch with One Click
Double-click `start_krshibandhu.bat` in this folder, or open PowerShell/Terminal:

```powershell
cd KrshiBandhu
.venv\Scripts\python.exe run.py
```

The web dashboard will automatically open in your browser at:
`http://127.0.0.1:8000`

---

## Project Structure

```
KrshiBandhu/
├── app/
│   ├── main.py              # FastAPI backend, REST endpoints, MJPEG & WebSockets
│   ├── engine.py            # Main pipeline (Camera -> Detector -> Trigger -> Outputs)
│   ├── detector.py          # YOLO-World open-vocabulary model
│   ├── trigger.py           # 3-of-5 voting filter, cooldown & human safety veto
│   ├── camera.py            # OpenCV threaded capture & low-light boost
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
│   ├── js/app.js            # Dashboard logic & WebSockets
│   ├── js/i18n.js           # English & Hindi translations
│   ├── img/logo.svg
│   └── vendor/chart.umd.min.js
├── tests/                   # Automated unit & integration tests
│   ├── test_trigger.py
│   ├── test_config.py
│   ├── test_storage.py
│   ├── test_api.py
│   └── smoke_detector.py
├── run.py                   # CLI & browser auto-launcher
├── start_krshibandhu.bat    # Windows 1-click startup script
└── requirements.txt
```

---

## Testing (जाँच)

Run all unit tests:
```powershell
.venv\Scripts\python.exe -m pytest -q
```
All 27 automated tests cover voting logic, sound playback, settings persistence, human suppression, API endpoints, snapshot storage, and WebSocket streaming.

---

## Farm Deployment Tips (खेत में उपयोग के सुझाव)

1. **Camera Placement:** Mount your webcam or night-vision USB camera under a covered shelter facing the crop entry point.
2. **Speakers:** Connect an external powered speaker or horn speaker to your PC's 3.5mm audio jack or Bluetooth for high volume across the field.
3. **Night Raids:** Enable the *Low-light boost* switch in the Settings tab, or plug in an IR USB camera (it works automatically with zero code changes).
4. **Telegram Alerts:** To receive photos on your phone, open Telegram, search `@BotFather`, create a bot to get your API Token, and paste it along with your Chat ID in the Settings tab.
