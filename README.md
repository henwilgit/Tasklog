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

## Authentication

By default (running locally with `python app.py`), TaskLog has **no login** — fine for a
home Wi-Fi setup where only your devices can reach it.

If you set the `TASKLOG_USERNAME` and `TASKLOG_PASSWORD` environment variables, every page
and API endpoint requires HTTP Basic Auth with those credentials. Set both when deploying
somewhere reachable from the internet (see below) — leave them unset for local-only use.

---

## Deploying to PythonAnywhere

[PythonAnywhere](https://www.pythonanywhere.com) gives a free account with **persistent
storage** (your `tasklog.db` survives reloads/restarts) and HTTPS out of the box — good fit
for this app since it uses SQLite on disk.

### 1. Get the code onto PythonAnywhere

Open a **Bash console** (Dashboard → New console → Bash) and clone your repo:

```bash
git clone <your-repo-url> tasklog
cd tasklog
```

(No GitHub repo yet? Use the **Files** tab to upload the project as a zip and unzip it
in the Bash console with `unzip yourfile.zip`.)

### 2. Create a virtualenv and install dependencies

```bash
mkvirtualenv --python=python3.11 tasklog-venv
pip install -r requirements.txt
```

### 3. Create the web app

- Go to the **Web** tab → **Add a new web app**
- Choose **Manual configuration** (not "Flask") → pick the same Python version as your venv
- Set:
  - **Source code**: `/home/<youruser>/tasklog`
  - **Working directory**: `/home/<youruser>/tasklog`
  - **Virtualenv**: `/home/<youruser>/.virtualenvs/tasklog-venv`

### 4. Edit the WSGI configuration file

Click the WSGI config file link on the **Web** tab and replace its contents with:

```python
import sys
import os

path = '/home/<youruser>/tasklog'
if path not in sys.path:
    sys.path.insert(0, path)

# Required for any internet-facing deployment — pick your own credentials
os.environ['TASKLOG_USERNAME'] = 'youruser'
os.environ['TASKLOG_PASSWORD'] = 'a-strong-password'

from app import app as application
```

### 5. Reload and open the app

Hit the green **Reload** button on the **Web** tab, then visit
`https://<youruser>.pythonanywhere.com` — your browser will prompt for the
username/password you set above.
