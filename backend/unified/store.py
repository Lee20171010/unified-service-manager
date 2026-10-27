"""SQLite is the only durable state owner. Each write uses its own transaction."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager


def identifier():
    return uuid.uuid4().hex


def now():
    return int(time.time() * 1000)


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entities (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, target_key TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(target_key) WHERE status IN ('queued','running');
                CREATE TABLE IF NOT EXISTS logs (seq INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL, time INTEGER NOT NULL, stream TEXT NOT NULL, text TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS job_log ON logs(job,seq);
                INSERT OR IGNORE INTO metadata VALUES ('schema_version','1');
            """
            )
            version = db.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()[0]
            if version != "1":
                raise RuntimeError(
                    "Unsupported database schema; restore a compatible version"
                )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, kind):
        with self.connect() as db:
            return [
                json.loads(r["body"])
                for r in db.execute(
                    "SELECT body FROM entities WHERE kind=? ORDER BY rowid", (kind,)
                )
            ]

    def get(self, kind, id):
        with self.connect() as db:
            r = db.execute(
                "SELECT body FROM entities WHERE kind=? AND id=?", (kind, id)
            ).fetchone()
            if r is None:
                raise KeyError(id)
            return json.loads(r["body"])

    def put(self, kind, body):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO entities VALUES (?,?,?)",
                (kind, body["id"], json.dumps(body)),
            )
        return body

    def add(self, kind, body):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            items = [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM entities WHERE kind=?", (kind,))
            ]
            if any(
                (
                    x["name"].casefold() == body["name"].casefold()
                    and (kind == "hosts" or x["host"] == body["host"])
                )
                or (
                    kind == "services"
                    and x["host"] == body["host"]
                    and (
                        x.get("adapter", "compose") == body.get("adapter", "compose")
                        or (
                            x.get("kind") in ("package", "extension")
                            and body.get("kind") in ("package", "extension")
                        )
                    )
                    and x.get("target_identity", x.get("compose_dir"))
                    == body["target_identity"]
                )
                for x in items
            ):
                raise Conflict("同名項目或相同接入目標已登記")
            db.execute(
                "INSERT INTO entities VALUES (?,?,?)",
                (kind, body["id"], json.dumps(body)),
            )
        return body

    def create_job(self, body):
        try:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                keys = set(body.get("locks", [body["target_key"]]))
                for row in db.execute(
                    "SELECT body FROM jobs WHERE status IN ('queued','running')"
                ):
                    active = json.loads(row[0])
                    if keys.intersection(active.get("locks", [active["target_key"]])):
                        raise Conflict("關聯目標已有執行中的任務")
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?)",
                    (body["id"], body["target_key"], body["status"], json.dumps(body)),
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict("此目標已有執行中的任務") from exc
        return body

    def update_job(self, body):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status=?,body=? WHERE id=?",
                (body["status"], json.dumps(body), body["id"]),
            )
            if body["status"] == "failed" and body.get("resource_type") == "service":
                row = db.execute(
                    "SELECT body FROM entities WHERE kind='services' AND id=?",
                    (body["resource_id"],),
                ).fetchone()
                if row:
                    service = json.loads(row[0])
                    service["status"] = "unknown"
                    db.execute(
                        "UPDATE entities SET body=? WHERE kind='services' AND id=?",
                        (json.dumps(service), service["id"]),
                    )

    def jobs(self):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM jobs ORDER BY rowid DESC")
            ]

    def job(self, id):
        with self.connect() as db:
            row = db.execute("SELECT body FROM jobs WHERE id=?", (id,)).fetchone()
            if row is None:
                raise KeyError(id)
            return json.loads(row[0])

    def log(self, id, stream, text):
        # Persist every chunk, including lines longer than a terminal viewport.
        with self.connect() as db:
            db.execute(
                "INSERT INTO logs(job,time,stream,text) VALUES (?,?,?,?)",
                (id, now(), stream, text),
            )

    def logs(self, id, after=0, limit=1000):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT seq,time,stream,text FROM logs WHERE job=? AND seq>? ORDER BY seq LIMIT ?",
                    (id, after, limit),
                )
            ]

    def recover(self):
        for j in self.jobs():
            if j["status"] in ("queued", "running"):
                j.update(
                    status="failed",
                    finished=now(),
                    error="SERVER_RESTARTED: 執行結果不確定，請先重新整理目標狀態；不會自動重試。",
                )
                self.log(j["id"], "stderr", j["error"])
                self.update_job(j)
