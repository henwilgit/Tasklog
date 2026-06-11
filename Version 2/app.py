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
                priority INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        # Add priority column if upgrading from old schema
        try:
            conn.execute('ALTER TABLE entries ADD COLUMN priority INTEGER NOT NULL DEFAULT 0')
        except:
            pass
        conn.commit()


def daily_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    backup_path = os.path.join(BACKUP_DIR, f'tasklog_{today}.db')
    if not os.path.exists(backup_path):
        shutil.copy2(DB_PATH, backup_path)
        backups = sorted(os.listdir(BACKUP_DIR))
        for old in backups[:-30]:
            os.remove(os.path.join(BACKUP_DIR, old))
        print(f"📦  Backup saved: backups/tasklog_{today}.db")


def next_priority(conn, date, entry_type):
    row = conn.execute(
        'SELECT MAX(priority) as mp FROM entries WHERE date = ? AND type = ?',
        (date, entry_type)
    ).fetchone()
    return (row['mp'] or 0) + 1


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
            rows = conn.execute(
                'SELECT * FROM entries WHERE date = ? ORDER BY type, priority ASC',
                (date,)
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
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        p = next_priority(conn, data['date'], data['type'])
        cur = conn.execute(
            'INSERT INTO entries (date, type, priority, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
            (data['date'], data['type'], p, data['text'], now, now)
        )
        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    data = request.json
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        existing = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404

        new_type = data['type']
        old_type = existing['type']

        # If type changed, assign next priority in new list
        if new_type != old_type:
            new_priority = next_priority(conn, existing['date'], new_type)
        else:
            new_priority = existing['priority']

        conn.execute(
            'UPDATE entries SET type = ?, text = ?, priority = ?, updated_at = ? WHERE id = ?',
            (new_type, data['text'], new_priority, now, entry_id)
        )
        conn.commit()
        row = conn.execute('SELECT * FROM entries WHERE id = ?', (entry_id,)).fetchone()
        return jsonify(dict(row))


@app.route('/api/entries/<int:entry_id>/move', methods=['POST'])
def move_entry(entry_id):
    """Move entry up or down within its type list for a given date."""
    direction = request.json.get('direction')  # 'up' or 'down'
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
        now = datetime.utcnow().isoformat()
        conn.execute('UPDATE entries SET priority = ?, updated_at = ? WHERE id = ?',
                     (swap['priority'], now, entry_id))
        conn.execute('UPDATE entries SET priority = ?, updated_at = ? WHERE id = ?',
                     (entry['priority'], now, swap_id))
        conn.commit()

        rows = conn.execute(
            'SELECT * FROM entries WHERE date = ? ORDER BY type, priority ASC',
            (entry['date'],)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


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
