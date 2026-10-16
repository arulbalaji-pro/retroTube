import sqlite3
import time
import random
import urllib.request
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), "retrotube.db")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "artifish/llama3.2-uncensored:latest"

NAMES_POOL = {
    "support": ["RetroFan", "Aarav", "PixelSamurai", "NostalgiaLover", "CyberKnight", "Maya"],
    "critic": ["TechReviewer", "FilmSnob99", "LogicSeeker", "CynicOne"],
    "curious": ["CuriousCat", "VintageHunter", "Anon2008", "ExplorerX"],
    "toxic": ["EdgeLord42", "HaterBot", "RageBaiter"]
}

def log(msg):
    print(f"[Worker] {msg}", flush=True)

def schedule_video_if_needed(video_id, title):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT (SELECT COUNT(*) FROM comments WHERE video_id = ?) + (SELECT COUNT(*) FROM scheduled_tasks WHERE video_id = ?)", (video_id, video_id))
        total_existing = cur.fetchone()[0]

        if total_existing == 0:
            total = random.randint(4, 8)
            half = (total + 1) // 2
            types = ["support"] * half
            others = ["critic", "curious", "toxic"]
            for _ in range(total - half):
                types.append(random.choice(others))
            random.shuffle(types)

            now = time.time()
            for ai_type in types:
                now += random.randint(15, 45)
                username = random.choice(NAMES_POOL[ai_type])
                stars = random.choice([4, 5]) if ai_type == "support" else (3 if ai_type == "curious" else random.choice([1, 2]))
                cur.execute("""
                    INSERT INTO scheduled_tasks (video_id, username, ai_type, stars, prompt, scheduled_time, executed)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (video_id, username, ai_type, stars, title, now))
            conn.commit()
            log(f"New video registered: '{title}'. Queued {total} comments.")
        conn.close()
    except Exception as e:
        log(f"Scheduling error: {e}")

class CommentsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/comments":
            qs = parse_qs(parsed.query)
            vid_id = qs.get("id", ["default"])[0]
            vid_title = qs.get("title", [vid_id])[0]

            schedule_video_if_needed(vid_id, vid_title)

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT username, ai_type, stars, comment, created_at FROM comments WHERE video_id = ? ORDER BY id ASC", (vid_id,))
            rows = cur.fetchall()
            conn.close()

            comments = [
                {"username": r[0], "ai_type": r[1], "stars": r[2], "comment": r[3], "created_at": r[4]}
                for r in rows
            ]

            data = json.dumps({"comments": comments}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def start_http_server():
    server = HTTPServer(("0.0.0.0", 5055), CommentsHandler)
    server.serve_forever()

def call_ollama(prompt, ai_type):
    sys_prompt = f"You are a commenter on YouTube in the late 2000s (2007-2009). Your personality is {ai_type}. Keep your response concise (1 to 2 sentences max). Write realistically like a forum or YouTube user from that era. Do not prefix with quotes."
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{sys_prompt}\n\nVideo topic: {prompt}\nComment:",
        "stream": False
    }
    try:
        req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as res:
            data = json.loads(res.read().decode())
            return data.get("response", "").strip()
    except Exception as e:
        log(f"Ollama inference error: {e}")
        fallbacks = {
            "support": "Awesome video! 5 stars!",
            "critic": "Pacing could be better honestly.",
            "curious": "What song or distro is this?",
            "toxic": "Overrated."
        }
        return fallbacks.get(ai_type, "Nice upload.")

def run_worker():
    log("RetroTube AI comment engine active. Monitoring queue...")
    last_status_time = 0

    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            now = time.time()

            cur.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE executed = 0")
            pending_total = cur.fetchone()[0]

            cur.execute("""
                SELECT id, video_id, username, ai_type, stars, prompt, scheduled_time 
                FROM scheduled_tasks 
                WHERE executed = 0 
                ORDER BY scheduled_time ASC 
                LIMIT 1
            """)
            next_task = cur.fetchone()

            if next_task:
                task_id, vid, uname, ai_type, stars, prompt, sched_time = next_task
                delay_remaining = int(sched_time - now)

                if delay_remaining <= 0:
                    log(f"Executing task #{task_id} | Video: '{prompt}' | Author: {uname} ({ai_type.upper()}, {stars}★)")
                    text = call_ollama(prompt, ai_type)
                    cur.execute("""
                        INSERT INTO comments (video_id, username, ai_type, stars, comment)
                        VALUES (?, ?, ?, ?, ?)
                    """, (vid, uname, ai_type, stars, text))
                    cur.execute("UPDATE scheduled_tasks SET executed = 1 WHERE id = ?", (task_id,))
                    conn.commit()
                    log(f"Success! {uname} commented: \"{text}\"")
                else:
                    if now - last_status_time >= 15:
                        log(f"Queue: {pending_total} pending | Next comment by '{uname}' scheduled in {delay_remaining}s...")
                        last_status_time = now
            else:
                if now - last_status_time >= 30:
                    log("Queue idle (0 pending tasks). Waiting for video click...")
                    last_status_time = now

            conn.close()
        except Exception as e:
            log(f"Worker Loop Error: {e}")

        time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()
    run_worker()
