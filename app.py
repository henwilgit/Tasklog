from flask import Flask, request, jsonify, send_from_directory, Response, session, redirect
import sqlite3
import os
import shutil
import hmac
from datetime import datetime, date, timedelta, timezone
import calendar

app = Flask(__name__, static_folder='static')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'tasklog.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
app.config['DATABASE'] = DB_PATH
app.secret_key = os.environ.get('TASKLOG_SECRET_KEY') or os.environ.get('TASKLOG_PASSWORD', 'dev-only-not-for-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)


def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('todo', 'done')),
                priority INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                classify TEXT NOT NULL DEFAULT '',
                recur_id TEXT,
                recur_rule TEXT,
                recur_end_date TEXT,
                recur_remaining INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        # Add new columns if upgrading
        for col, defn in [
            ('priority', 'INTEGER NOT NULL DEFAULT 0'),
            ('classify', "TEXT NOT NULL DEFAULT ''"),
            ('recur_id', 'TEXT'),
            ('recur_rule', 'TEXT'),
            ('recur_end_date', 'TEXT'),
            ('recur_remaining', 'INTEGER'),
        ]:
            try:
                conn.execute(f'ALTER TABLE entries ADD COLUMN {col} {defn}')
            except:
                pass

        conn.execute('''
            CREATE TABLE IF NOT EXISTS classify_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT UNIQUE NOT NULL
            )
        ''')
        conn.commit()


init_db()


def daily_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    backup_path = os.path.join(BACKUP_DIR, f'tasklog_{today}.db')
    if not os.path.exists(backup_path):
        shutil.copy2(app.config['DATABASE'], backup_path)
        backups = sorted(os.listdir(BACKUP_DIR))
        for old in backups[:-30]:
            os.remove(os.path.join(BACKUP_DIR, old))
        print(f"📦  Backup saved: backups/tasklog_{today}.db")


def next_priority(conn, date_str, entry_type):
    row = conn.execute(
        'SELECT MAX(priority) as mp FROM entries WHERE date = ? AND type = ?',
        (date_str, entry_type)
    ).fetchone()
    return (row['mp'] or 0) + 1


def parse_date(s):
    """Parse CCYYMMDD string to date object."""
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def fmt_date(d):
    """Format date object to CCYYMMDD string."""
    return d.strftime('%Y%m%d')


def next_occurrence(rule, from_date):
    """Calculate next occurrence date given a recurrence rule and a base date."""
    d = parse_date(from_date)

    if rule == 'daily':
        return fmt_date(d + timedelta(days=1))
    elif rule == 'weekly':
        return fmt_date(d + timedelta(weeks=1))
    elif rule == 'monthly':
        # Same day next month
        month = d.month + 1 if d.month < 12 else 1
        year = d.year if d.month < 12 else d.year + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return fmt_date(date(year, month, day))
    elif rule == 'quarterly':
        month = d.month + 3
        year = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return fmt_date(date(year, month, day))
    elif rule == 'annually':
        year = d.year + 1
        day = min(d.day, calendar.monthrange(year, d.month)[1])
        return fmt_date(date(year, d.month, day))
    elif rule and rule.startswith('lastday:'):
        # lastday:TUE  = last Tuesday of month
        weekday_map = {'MON':0,'TUE':1,'WED':2,'THU':3,'FRI':4,'SAT':5,'SUN':6}
        parts = rule.split(':')
        weekday = weekday_map.get(parts[1].upper(), 0)
        # Move to next month
        month = d.month + 1 if d.month < 12 else 1
        year = d.year if d.month < 12 else d.year + 1
        # Find last weekday in that month
        last_day = calendar.monthrange(year, month)[1]
        for day in range(last_day, last_day - 7, -1):
            if date(year, month, day).weekday() == weekday:
                return fmt_date(date(year, month, day))
    elif rule and rule.startswith('firstday:'):
        weekday_map = {'MON':0,'TUE':1,'WED':2,'THU':3,'FRI':4,'SAT':5,'SUN':6}
        parts = rule.split(':')
        weekday = weekday_map.get(parts[1].upper(), 0)
        month = d.month + 1 if d.month < 12 else 1
        year = d.year if d.month < 12 else d.year + 1
        for day in range(1, 8):
            if date(year, month, day).weekday() == weekday:
                return fmt_date(date(year, month, day))

    return None


def save_classify(conn, value):
    if value and value.strip():
        try:
            conn.execute('INSERT OR IGNORE INTO classify_values (value) VALUES (?)', (value.strip(),))
        except:
            pass


def _check_auth(username, password):
    """Validate credentials against TASKLOG_USERNAME/TASKLOG_PASSWORD env vars.

    If those env vars aren't set, auth is disabled (e.g. local home-Wi-Fi use).
    """
    expected_user = os.environ.get('TASKLOG_USERNAME')
    expected_pass = os.environ.get('TASKLOG_PASSWORD')
    if not expected_user or not expected_pass:
        return True
    return (
        hmac.compare_digest(username, expected_user)
        and hmac.compare_digest(password, expected_pass)
    )


LOGIN_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>TaskLog</title>
<link rel="icon" type="image/png" href="/static/apple-touch-icon.png">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<meta name="theme-color" content="#22C55E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'DM Sans', sans-serif; background: #F7F6F1; color: #1A1917;
    min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px;
  }
  .card {
    background: #FFFFFF; border: 1px solid #E2E0D8; border-radius: 12px;
    padding: 32px 24px; width: 100%; max-width: 320px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }
  .logo { font-family: 'DM Serif Display', serif; font-size: 24px; text-align: center; margin-bottom: 24px; }
  label { display: block; font-size: 13px; font-weight: 500; color: #6B6960; margin-bottom: 6px; }
  input {
    width: 100%; border: 1px solid #E2E0D8; border-radius: 8px; padding: 10px 12px;
    font-size: 15px; font-family: 'DM Sans', sans-serif; outline: none; margin-bottom: 16px;
  }
  input:focus { border-color: #1A1917; }
  button {
    width: 100%; border: none; border-radius: 8px; padding: 12px; font-size: 15px;
    font-weight: 600; font-family: 'DM Sans', sans-serif; background: #22C55E; color: #FFFFFF; cursor: pointer;
  }
  button:active { background: #16A34A; }
  .error { color: #B91C1C; font-size: 13px; margin-bottom: 16px; text-align: center; }
</style>
</head>
<body>
<form class="card" method="POST" action="/login">
  <div class="logo">TaskLog</div>
  __ERROR__
  <label for="username">Username</label>
  <input type="text" id="username" name="username" autocomplete="username" autocapitalize="none" autocorrect="off" required autofocus>
  <label for="password">Password</label>
  <input type="password" id="password" name="password" autocomplete="current-password" required>
  <button type="submit">Log in</button>
</form>
</body>
</html>'''


@app.before_request
def _require_auth():
    if app.config.get('TESTING'):
        return
    if request.path.startswith('/static/'):
        # Static assets (icons, CSS/JS) contain no task data, and iOS's
        # "Add to Home Screen" icon fetcher doesn't send Basic Auth credentials.
        return
    if not os.environ.get('TASKLOG_USERNAME') or not os.environ.get('TASKLOG_PASSWORD'):
        return
    if request.path == '/login':
        return
    if session.get('authenticated'):
        return
    auth = request.authorization
    if auth and _check_auth(auth.username, auth.password):
        return
    if request.path.startswith('/api/'):
        return Response(
            'Authentication required', 401,
            {'WWW-Authenticate': 'Basic realm="TaskLog"'}
        )
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error_html = ''
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if _check_auth(username, password):
            session.permanent = True
            session['authenticated'] = True
            return redirect('/')
        error_html = '<div class="error">Incorrect username or password</div>'
    return Response(LOGIN_PAGE.replace('__ERROR__', error_html), mimetype='text/html')


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/classify', methods=['GET'])
def get_classify_values():
    with get_db() as conn:
        rows = conn.execute('SELECT value FROM classify_values ORDER BY value ASC').fetchall()
        return jsonify([r['value'] for r in rows])


@app.route('/api/entries', methods=['GET'])
def get_entries():
    date_str = request.args.get('date')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    entry_type = request.args.get('type')

    with get_db() as conn:
        if date_str:
            rows = conn.execute(
                'SELECT * FROM entries WHERE date = ? ORDER BY type, priority ASC',
                (date_str,)
            ).fetchall()
        elif date_from and date_to:
            query = 'SELECT * FROM entries WHERE date >= ? AND date <= ?'
            params = [date_from, date_to]
            if entry_type in ('todo', 'done'):
                query += ' AND type = ?'
                params.append(entry_type)
            query += ' ORDER BY date ASC, type, priority ASC'
            rows = conn.execute(query, params).fetchall()
        else:
            return jsonify({'error': 'Provide date or from/to params'}), 400
        return jsonify([dict(r) for r in rows])


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.json
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        p = next_priority(conn, data['date'], data['type'])
        recur_id = data.get('recur_id')
        recur_rule = data.get('recur_rule') or None
        recur_end_date = data.get('recur_end_date') or None
        recur_remaining = data.get('recur_remaining')
        if recur_remaining is not None:
            recur_remaining = int(recur_remaining)
        classify = data.get('classify', '')
        save_classify(conn, classify)

        # Generate recur_id for new recurring series
        if recur_rule and not recur_id:
            import uuid
            recur_id = str(uuid.uuid4())

        cur = conn.execute(
            '''INSERT INTO entries
               (date, type, priority, text, classify, recur_id, recur_rule, recur_end_date, recur_remaining, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['date'], data['type'], p, data['text'], classify,
             recur_id, recur_rule, recur_end_date, recur_remaining, now, now)
        )
        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    data = request.json
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        existing = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404

        new_type = data['type']
        old_type = existing['type']
        new_date = data.get('date', existing['date'])
        old_date = existing['date']
        classify = data.get('classify', existing['classify'] or '')
        save_classify(conn, classify)

        recur_rule = data.get('recur_rule', existing['recur_rule'])
        recur_end_date = data.get('recur_end_date', existing['recur_end_date'])
        recur_remaining = data.get('recur_remaining', existing['recur_remaining'])

        if new_type != old_type or new_date != old_date:
            new_priority = next_priority(conn, new_date, new_type)
        else:
            new_priority = existing['priority']

        conn.execute(
            '''UPDATE entries SET date=?, type=?, text=?, classify=?, priority=?,
               recur_rule=?, recur_end_date=?, recur_remaining=?, updated_at=? WHERE id=?''',
            (new_date, new_type, data['text'], classify, new_priority,
             recur_rule, recur_end_date, recur_remaining, now, entry_id)
        )

        # If promoting todo->done and entry is recurring, create next occurrence
        next_entry = None
        if old_type == 'todo' and new_type == 'done' and existing['recur_rule']:
            next_date = next_occurrence(existing['recur_rule'], old_date)
            can_create = False
            if next_date:
                # Check end date
                if existing['recur_end_date']:
                    if next_date <= existing['recur_end_date']:
                        can_create = True
                elif existing['recur_remaining'] is not None:
                    if existing['recur_remaining'] > 1:
                        can_create = True
                else:
                    can_create = True

            if can_create:
                new_remaining = (existing['recur_remaining'] - 1) if existing['recur_remaining'] is not None else None
                p2 = next_priority(conn, next_date, 'todo')
                cur2 = conn.execute(
                    '''INSERT INTO entries
                       (date, type, priority, text, classify, recur_id, recur_rule, recur_end_date, recur_remaining, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (next_date, 'todo', p2, existing['text'], existing['classify'] or '',
                     existing['recur_id'], existing['recur_rule'], existing['recur_end_date'],
                     new_remaining, now, now)
                )
                next_row = conn.execute('SELECT * FROM entries WHERE id = ?', (cur2.lastrowid,)).fetchone()
                next_entry = dict(next_row)

        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        result = dict(row)
        if next_entry:
            result['next_entry'] = next_entry
        return jsonify(result)


@app.route('/api/entries/<int:entry_id>/move', methods=['POST'])
def move_entry(entry_id):
    direction = request.json.get('direction')
    with get_db() as conn:
        entry = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        if not entry:
            return jsonify({'error': 'Not found'}), 404
        siblings = conn.execute(
            'SELECT * FROM entries WHERE date = ? AND type = ? ORDER BY priority ASC',
            (entry['date'], entry['type'])
        ).fetchall()
        ids = [r['id'] for r in siblings]
        idx = ids.index(entry_id)
        if direction == 'up' and idx > 0:
            swap_id = ids[idx - 1]
        elif direction == 'down' and idx < len(ids) - 1:
            swap_id = ids[idx + 1]
        else:
            return jsonify({'message': 'Already at boundary'}), 200
        swap = conn.execute('SELECT * FROM entries WHERE id = ?', (swap_id,)).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute('UPDATE entries SET priority=?, updated_at=? WHERE id=?', (swap['priority'], now, entry_id))
        conn.execute('UPDATE entries SET priority=?, updated_at=? WHERE id=?', (entry['priority'], now, swap_id))
        conn.commit()
        rows = conn.execute(
            'SELECT * FROM entries WHERE date = ? ORDER BY type, priority ASC',
            (entry['date'],)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    scope = request.args.get('scope', 'single')  # 'single' or 'all'
    with get_db() as conn:
        entry = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        if not entry:
            return jsonify({'error': 'Not found'}), 404
        if scope == 'all' and entry['recur_id']:
            conn.execute('DELETE FROM entries WHERE recur_id = ?', (entry['recur_id'],))
        else:
            conn.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
        conn.commit()
        return jsonify({'deleted': entry_id, 'scope': scope})


if __name__ == '__main__':
    daily_backup()
    port = int(os.environ.get('PORT', 5000))
    print(f"\n✅  TaskLog running at http://localhost:{port}")
    print(f"📱  On your phone (same Wi-Fi), go to http://<YOUR-PC-IP>:{port}")
    print("📦  Backups are saved automatically in the 'backups' folder\n")
    app.run(host='0.0.0.0', port=port, debug=False)
