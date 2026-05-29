"""Per-user store + auth for musify (SQLite, stdlib only).

Users sign up with username/password + seed favorites (artists/genres). Their
library (liked songs, playlists), recently-played, and seeds drive a personalized
home. Tracks are stored as JSON blobs.
"""
import os
import json
import time
import sqlite3
import hashlib
import secrets
import threading

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'musify.db')
_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY, salt TEXT, hash TEXT,
            seeds TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY, username TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS liked(
            username TEXT, tid TEXT, track TEXT, ts REAL,
            PRIMARY KEY(username, tid));
        CREATE TABLE IF NOT EXISTS playlists(
            id TEXT PRIMARY KEY, username TEXT, name TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS playlist_tracks(
            pid TEXT, tid TEXT, track TEXT, ts REAL,
            PRIMARY KEY(pid, tid));
        CREATE TABLE IF NOT EXISTS played(
            username TEXT, tid TEXT, track TEXT, ts REAL,
            PRIMARY KEY(username, tid));
        """)


# ---- auth ----
def _hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 120000).hex()


def create_user(username, password, seeds):
    username = (username or '').strip()
    if not username or not password:
        raise ValueError('username and password required')
    salt = secrets.token_hex(16)
    with _lock, _conn() as c:
        if c.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            raise ValueError('username taken')
        c.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                  (username, salt, _hash(password, salt), json.dumps(seeds or []), time.time()))
    return new_session(username)


def verify(username, password):
    with _lock, _conn() as c:
        r = c.execute('SELECT salt, hash FROM users WHERE username=?', (username,)).fetchone()
    return bool(r) and secrets.compare_digest(r['hash'], _hash(password, r['salt']))


def new_session(username):
    tok = secrets.token_urlsafe(24)
    with _lock, _conn() as c:
        c.execute('INSERT INTO sessions VALUES(?,?,?)', (tok, username, time.time()))
    return tok


def user_for_token(tok):
    if not tok:
        return None
    with _lock, _conn() as c:
        r = c.execute('SELECT username FROM sessions WHERE token=?', (tok,)).fetchone()
    return r['username'] if r else None


def drop_session(tok):
    with _lock, _conn() as c:
        c.execute('DELETE FROM sessions WHERE token=?', (tok,))


def get_user(username):
    with _lock, _conn() as c:
        r = c.execute('SELECT username, seeds FROM users WHERE username=?', (username,)).fetchone()
    if not r:
        return None
    return {'username': r['username'], 'seeds': json.loads(r['seeds'] or '[]')}


# ---- library ----
def like(username, track):
    with _lock, _conn() as c:
        c.execute('INSERT OR REPLACE INTO liked VALUES(?,?,?,?)',
                  (username, str(track.get('id')), json.dumps(track), time.time()))


def unlike(username, tid):
    with _lock, _conn() as c:
        c.execute('DELETE FROM liked WHERE username=? AND tid=?', (username, str(tid)))


def liked(username):
    with _lock, _conn() as c:
        rows = c.execute('SELECT track FROM liked WHERE username=? ORDER BY ts DESC', (username,)).fetchall()
    return [json.loads(r['track']) for r in rows]


def is_liked(username, tid):
    with _lock, _conn() as c:
        return bool(c.execute('SELECT 1 FROM liked WHERE username=? AND tid=?',
                              (username, str(tid))).fetchone())


def create_playlist(username, name):
    pid = secrets.token_hex(8)
    with _lock, _conn() as c:
        c.execute('INSERT INTO playlists VALUES(?,?,?,?)', (pid, username, name or 'New Playlist', time.time()))
    return pid


def add_to_playlist(pid, track):
    with _lock, _conn() as c:
        c.execute('INSERT OR REPLACE INTO playlist_tracks VALUES(?,?,?,?)',
                  (pid, str(track.get('id')), json.dumps(track), time.time()))


def playlists(username):
    with _lock, _conn() as c:
        pls = c.execute('SELECT id, name FROM playlists WHERE username=? ORDER BY created DESC',
                        (username,)).fetchall()
        out = []
        for p in pls:
            tr = c.execute('SELECT track FROM playlist_tracks WHERE pid=? ORDER BY ts', (p['id'],)).fetchall()
            tracks = [json.loads(t['track']) for t in tr]
            out.append({'id': p['id'], 'name': p['name'], 'tracks': tracks,
                        'cover': tracks[0]['cover'] if tracks else ''})
    return out


def record_played(username, track):
    with _lock, _conn() as c:
        c.execute('INSERT OR REPLACE INTO played VALUES(?,?,?,?)',
                  (username, str(track.get('id')), json.dumps(track), time.time()))
        # keep last 50
        c.execute("""DELETE FROM played WHERE username=? AND tid NOT IN
                     (SELECT tid FROM played WHERE username=? ORDER BY ts DESC LIMIT 50)""",
                  (username, username))


def recent(username, n=20):
    with _lock, _conn() as c:
        rows = c.execute('SELECT track FROM played WHERE username=? ORDER BY ts DESC LIMIT ?',
                         (username, n)).fetchall()
    return [json.loads(r['track']) for r in rows]
