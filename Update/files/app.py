from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
import shutil
from datetime import datetime

app = Flask(__name__, static_folder='static')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'tasklog.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('todo', 'done')),
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()


def daily_backup():
    """Make a dated backup of the database once per day."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    backup_path = os.path.join(BACKUP_DIR, f'tasklog_{today}.db')
    if not os.path.exists(backup_path):
        shutil.copy2(DB_PATH, backup_path)
        # Keep only the last 30 backups
        backups = sorted(os.listdir(BACKUP_DIR))
        for old in backups[:-30]:
            os.remove(os.path.join(BACKUP_DIR, old))
        print(f"📦  Backup saved: backups/tasklog_{today}.db")


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/entries', methods=['GET'])
def get_entries():
    date = request.args.get('date')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    entry_type = request.args.get('type')

    with get_db() as conn:
        if date:
            query = 'SELECT * FROM entries WHERE date = ? ORDER BY id ASC'
            params = [date]
        elif date_from and date_to:
            query = 'SELECT * FROM entries WHERE date >= ? AND date <= ?'
            params = [date_from, date_to]
            if entry_type in ('todo', 'done'):
                query += ' AND type = ?'
                params.append(entry_type)
            query += ' ORDER BY date ASC, id ASC'
        else:
            return jsonify({'error': 'Provide date or from/to params'}), 400

        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.json
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO entries (date, type, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
            (data['date'], data['type'], data['text'], now, now)
        )
        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    data = request.json
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            'UPDATE entries SET type = ?, text = ?, updated_at = ? WHERE id = ?',
            (data['type'], data['text'], now, entry_id)
        )
        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(row))


@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    with get_db() as conn:
        conn.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
        conn.commit()
        return jsonify({'deleted': entry_id})


if __name__ == '__main__':
    init_db()
    daily_backup()
    print("\n✅  TaskLog running at http://localhost:5000")
    print("📱  On your phone (same Wi-Fi), go to http://<YOUR-PC-IP>:5000")
    print("📦  Backups are saved automatically in the 'backups' folder\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
