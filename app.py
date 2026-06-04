"""
Мой планер — Киняева Ульяна
Flask API + PostgreSQL (Supabase)
"""

import os
import base64
import logging
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory, Response

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.pjincuzzpyroqolfflkf:paSqat-gadre4-cowhox@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
)
PORT = int(os.environ.get('PORT', 5000))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS my_tasks (
                id         SERIAL PRIMARY KEY,
                day        TEXT NOT NULL,
                time       TEXT DEFAULT '',
                task       TEXT NOT NULL,
                place      TEXT DEFAULT '',
                done       INTEGER DEFAULT 0,
                comment    TEXT DEFAULT '',
                deadline   TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)
        for col, defn in [
            ('comment',    "TEXT DEFAULT ''"),
            ('deadline',   "TEXT DEFAULT ''"),
            ('sort_order', 'INTEGER DEFAULT 0'),
        ]:
            cur.execute(f"ALTER TABLE my_tasks ADD COLUMN IF NOT EXISTS {col} {defn}")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS my_files (
                id         SERIAL PRIMARY KEY,
                task_id    INTEGER REFERENCES my_tasks(id) ON DELETE CASCADE,
                filename   TEXT NOT NULL,
                mimetype   TEXT DEFAULT 'application/octet-stream',
                data       TEXT NOT NULL,
                created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)
    conn.commit()
    conn.close()
    log.info("БД готова")

app = Flask(__name__, static_folder=".")

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,OPTIONS"
    return r

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ── Tasks ─────────────────────────────────────

@app.route("/api/tasks", methods=["GET", "OPTIONS"])
def get_tasks():
    if request.method == "OPTIONS": return "", 204
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM my_tasks ORDER BY day, sort_order, time")
        rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tasks", methods=["POST"])
def add_task():
    data   = request.get_json(force=True)
    day    = data.get("day", "")
    time   = data.get("time", "")
    task   = data.get("task", "").strip()
    place  = data.get("place", "").strip()
    done   = int(data.get("done", 0))
    comment  = data.get("comment", "")
    deadline = data.get("deadline", "")
    if not day or not task:
        return jsonify({"error": "day и task обязательны"}), 400
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO my_tasks (day,time,task,place,done,comment,deadline) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (day, time, task, place, done, comment, deadline)
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return jsonify({"id": new_id}), 201

@app.route("/api/tasks/<int:task_id>", methods=["PATCH", "OPTIONS"])
def update_task(task_id):
    if request.method == "OPTIONS": return "", 204
    data = request.get_json(force=True)
    conn = get_db()
    with conn.cursor() as cur:
        if 'done' in data:
            cur.execute("UPDATE my_tasks SET done=%s WHERE id=%s", (int(bool(data['done'])), task_id))
        if 'comment' in data:
            cur.execute("UPDATE my_tasks SET comment=%s WHERE id=%s", (data['comment'], task_id))
        if 'sort_order' in data:
            cur.execute("UPDATE my_tasks SET sort_order=%s WHERE id=%s", (data['sort_order'], task_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE", "OPTIONS"])
def delete_task(task_id):
    if request.method == "OPTIONS": return "", 204
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM my_tasks WHERE id=%s", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:task_id>/duplicate", methods=["POST"])
def duplicate_task(task_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM my_tasks WHERE id=%s", (task_id,))
        t = cur.fetchone()
        if not t:
            conn.close()
            return jsonify({"error": "Not found"}), 404
        cur.execute(
            "INSERT INTO my_tasks (day,time,task,place,done,comment,deadline) VALUES (%s,%s,%s,%s,0,%s,%s) RETURNING id",
            (t['day'], t['time'], t['task'], t['place'], t['comment'], t['deadline'])
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return jsonify({"id": new_id, "task": dict(t)}), 201

@app.route("/api/reorder", methods=["POST", "OPTIONS"])
def reorder_tasks():
    if request.method == "OPTIONS": return "", 204
    order = request.get_json(force=True).get("order", [])
    conn = get_db()
    with conn.cursor() as cur:
        for item in order:
            cur.execute("UPDATE my_tasks SET sort_order=%s WHERE id=%s", (item['sort_order'], item['id']))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ── Files ─────────────────────────────────────

@app.route("/api/tasks/<int:task_id>/files", methods=["GET"])
def get_files(task_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, mimetype, created_at FROM my_files WHERE task_id=%s ORDER BY id", (task_id,))
        rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tasks/<int:task_id>/files", methods=["POST"])
def upload_file(task_id):
    data     = request.get_json(force=True)
    filename = data.get("filename", "file")
    mimetype = data.get("mimetype", "application/octet-stream")
    file_b64 = data.get("data", "")
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO my_files (task_id,filename,mimetype,data) VALUES (%s,%s,%s,%s) RETURNING id",
            (task_id, filename, mimetype, file_b64)
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return jsonify({"id": new_id, "filename": filename}), 201

@app.route("/api/files/<int:file_id>", methods=["GET"])
def download_file(file_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM my_files WHERE id=%s", (file_id,))
        f = cur.fetchone()
    conn.close()
    if not f:
        return jsonify({"error": "Not found"}), 404
    file_bytes = base64.b64decode(f['data'])
    return Response(
        file_bytes,
        mimetype=f['mimetype'],
        headers={"Content-Disposition": f"attachment; filename=\"{f['filename']}\""}
    )

@app.route("/api/files/<int:file_id>", methods=["DELETE"])
def delete_file(file_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM my_files WHERE id=%s", (file_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)

