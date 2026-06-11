# TaskLog

A simple personal task journal — log To Do and Done entries by date, and run reports across date ranges.

---

## Quick Start (Windows)

### 1. Install Python
If you don't have Python, download it from https://python.org (3.11+ recommended).
Make sure to tick **"Add Python to PATH"** during install.

### 2. Set up the app

Open **Command Prompt** (Win+R → type `cmd` → Enter) and run:

```
cd path\to\tasklog
pip install -r requirements.txt
python app.py
```

You should see:
```
✅  TaskLog running at http://localhost:5000
📱  On your phone (same Wi-Fi), go to http://<YOUR-PC-IP>:5000
```

### 3. Open in your browser

Go to: **http://localhost:5000**

---

## Accessing from iPhone (same Wi-Fi)

1. Find your Windows PC's local IP:
   - Open Command Prompt → type `ipconfig`
   - Look for **IPv4 Address** under your Wi-Fi adapter (e.g. `192.168.1.42`)

2. On your iPhone browser, go to: `http://192.168.1.42:5000`

3. To add it to your home screen:
   - In Safari, tap the Share button → **Add to Home Screen**
   - It'll behave like an app!

> **Note**: Your PC must be on and the app must be running for phone access to work.

---

## Features

- **Entry screen**: Navigate by date (arrows or date picker), add To Do / Done entries
- **Promote**: Tap ✓ on any To Do to instantly move it to Done
- **Edit**: Change text or type of any entry
- **Report screen**: Pick a date range + filter (All / To Do / Done), see summary counts and all entries grouped by day

---

## Data

All data is stored in `tasklog.db` (SQLite) in the app folder. Back this file up to keep your history safe.

---

## Future: Deploy to the Cloud

When you want access from anywhere (not just home Wi-Fi):

1. Push this folder to GitHub
2. Deploy free on **Railway** (railway.app) or **Render** (render.com)
3. They'll give you a URL like `https://tasklog-xyz.railway.app` — works on any device

No code changes needed.
