import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'chat.db')
KEY_PATH = os.path.join(BASE_DIR, 'secret.key')
USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,20}$')


def load_secret_key():
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(KEY_PATH, 'w') as f:
        f.write(key)
    return key


app = Flask(__name__)
app.config['SECRET_KEY'] = load_secret_key()
app.permanent_session_lifetime = timedelta(days=7)
socketio = SocketIO(app, async_mode='threading')

online = {}  # socket id -> username


# ---------- Database ----------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def find_user(username):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
    finally:
        conn.close()


def create_user(username, password):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ---------- Pages ----------

@app.route('/')
def index():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    return render_template('index.html', username=username)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('username'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = find_user(username)
        if user and check_password_hash(user['password_hash'], password):
            session.permanent = True
            session['username'] = user['username']
            return redirect(url_for('index'))
        error = 'Wrong username or password.'

    return render_template('auth.html', mode='login', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if session.get('username'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not USERNAME_RE.match(username):
            error = 'Username must be 3-20 characters: letters, numbers or underscores.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif not create_user(username, password):
            error = 'That username is taken.'
        else:
            session.permanent = True
            session['username'] = find_user(username)['username']
            return redirect(url_for('index'))

    return render_template('auth.html', mode='signup', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- Real-time chat ----------

def online_names():
    return sorted(set(list(online.values())), key=str.lower)


def now():
    return datetime.now().strftime('%H:%M')


@socketio.on('connect')
def handle_connect():
    username = session.get('username')
    if not username:
        return False  # not logged in: reject the connection

    first_tab = username not in list(online.values())
    online[request.sid] = username
    emit('users', online_names(), broadcast=True)
    if first_tab:
        emit('system', f'{username} joined the chat', broadcast=True, include_self=False)


@socketio.on('message')
def handle_message(text):
    username = online.get(request.sid)
    text = str(text or '').strip()[:500]
    if not username or not text:
        return
    emit('message', {'user': username, 'text': text, 'time': now()}, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect(reason=None):
    username = online.pop(request.sid, None)
    if not username:
        return
    emit('users', online_names(), broadcast=True)
    if username not in list(online.values()):
        emit('system', f'{username} left the chat', broadcast=True)


if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)