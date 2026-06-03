"""
Мой планер — личный планер без бота
Flask API + PostgreSQL (Supabase)
"""

import os
import logging
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.pjincuzzpyroqolfflkf:paSqat-gadre4-cowhox@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
)
PORT = int(os.environ.get('PORT', 5000))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
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
                time       TEXT,
                task       TEXT NOT NULL,
                place      TEXT,
                done       INTEGER DEFAULT 0,
                created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)
    conn.commit()
    conn.close()
    log.info("База данных готова (my_tasks)")

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

@app.route("/api/tasks", methods=["GET", "OPTIONS"])
def get_tasks():
    if request.method == "OPTIONS":
        return "", 204
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM my_tasks ORDER BY day, time")
        rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tasks", methods=["POST"])
def add_task():
    data  = request.get_json(force=True)
    day   = data.get("day", "")
    time  = data.get("time", "")
    task  = data.get("task", "").strip()
    place = data.get("place", "").strip()
    done  = int(data.get("done", 0))
    if not day or not task:
        return jsonify({"error": "Поля day и task обязательны"}), 400
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO my_tasks (day,time,task,place,done) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (day, time, task, place, done)
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return jsonify({"id": new_id}), 201

@app.route("/api/tasks/<int:task_id>", methods=["PATCH", "OPTIONS"])
def update_task(task_id):
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True)
    done = int(bool(data.get("done", False)))
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("UPDATE my_tasks SET done=%s WHERE id=%s", (done, task_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE", "OPTIONS"])
def delete_task(task_id):
    if request.method == "OPTIONS":
        return "", 204
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM my_tasks WHERE id=%s", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)
