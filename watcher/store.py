"""Local persistent tasks and bounded event evidence; images never use caller paths."""
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import time


class WatchStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'watcher.sqlite3'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, task TEXT UNIQUE NOT NULL, plan TEXT NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL,
                before BLOB NOT NULL, after BLOB NOT NULL, time REAL NOT NULL, confidence REAL NOT NULL);''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def task_value(row):
        return dict(id=row['id'], task=row['task'], plan=json.loads(row['plan'])) if row else None

    def save_task(self, task, plan):
        with self.connect() as db:
            db.execute('INSERT INTO tasks(task,plan,updated) VALUES(?,?,?) ON CONFLICT(task) DO UPDATE SET updated=excluded.updated',
                       (task,json.dumps(plan),time.time()))
            return self.task_value(db.execute('SELECT * FROM tasks WHERE task=?',(task,)).fetchone())

    def task(self, task_id):
        with self.connect() as db:
            return self.task_value(db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone())

    def find_task(self, task):
        with self.connect() as db:
            return self.task_value(db.execute('SELECT * FROM tasks WHERE task=?',(task,)).fetchone())

    def active_task(self):
        with self.connect() as db:
            return self.task_value(db.execute('SELECT * FROM tasks ORDER BY updated DESC LIMIT 1').fetchone())

    def events(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT e.id,e.task_id,t.task,e.time,e.confidence FROM events e JOIN tasks t ON t.id=e.task_id ORDER BY e.id DESC')]

    def save_event(self, task_id, before, after, timestamp, confidence):
        if not math.isfinite(timestamp) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('Invalid event metadata')
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM tasks WHERE id=?',(task_id,)).fetchone():
                raise ValueError('Unknown task')
            result=db.execute('INSERT INTO events(task_id,before,after,time,confidence) VALUES(?,?,?,?,?)',
                             (task_id,before,after,timestamp,confidence))
            db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 100)')
            return result.lastrowid

    def image(self, event_id, which):
        if which not in ('before','after'):
            return None
        with self.connect() as db:
            row=db.execute(f'SELECT {which} FROM events WHERE id=?',(event_id,)).fetchone()
            return bytes(row[0]) if row else None

    def delete_event(self, event_id):
        with self.connect() as db:
            db.execute('DELETE FROM events WHERE id=?',(event_id,))

    def clear_events(self):
        with self.connect() as db:
            db.execute('DELETE FROM events')
