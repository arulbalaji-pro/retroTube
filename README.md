# RetroTube

Retro-styled video platform featuring an autonomous background AI worker engine that simulates organic community comments and ratings.

---

## Architecture

* **Frontend:** Dockerized Next.js interface on port `7004` (mapped to `3000`).
* **Background Worker:** Python daemon (`ai_worker.py`) managed via `systemd` (`retrotube-worker.service`).
* **HTTP Bridge:** Background API on port `5055`.
* **Database:** SQLite (`retrotube.db`).

---

## Quick Start

```bash
# 1. Start Docker container
docker compose up -d

# 2. Link & enable existing systemd worker service
mkdir -p ~/.config/systemd/user
cp retrotube-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now retrotube-worker.service
```

---

## Monitoring & CLI (~/.bashrc)

```bash
# RetroTube AI Stack
retrotube-status() {
  echo "================================================================="
  echo "                    RETROTUBE AI SYSTEM STATUS                   "
  echo "================================================================="
  systemctl --user is-active retrotube-worker.service --quiet && echo "  • retrotube-worker.service : ACTIVE (running)" || echo "  • retrotube-worker.service : INACTIVE / FAILED"
  curl -s -m 2 "[http://127.0.0.1:5055/comments?id=ping](http://127.0.0.1:5055/comments?id=ping)" > /dev/null && echo "  • Port 5055 Bridge          : ONLINE (responding)" || echo "  • Port 5055 Bridge          : OFFLINE"
  docker ps --filter "name=retro-tube" --format "  • {{.Names}} : {{.Status}} ({{.Ports}})" 2>/dev/null
  RT_DB="$HOME/retro-tube/retrotube.db"
  if [ -f "$RT_DB" ]; then
    sqlite3 "$RT_DB" "
      SELECT '  • Total Comments Posted    : ' || COUNT(*) FROM comments;
      SELECT '  • Tasks Pending Exec       : ' || COUNT(*) FROM scheduled_tasks WHERE executed = 0;
      SELECT '  • Average Rating Given     : ' || ROUND(AVG(stars), 2) || ' / 5.0' FROM comments;
    "
  fi
  echo "================================================================="
}

alias retrotube-logs='journalctl --user -u retrotube-worker.service -f'
alias retrotube-restart='systemctl --user restart retrotube-worker.service && docker compose -f ~/retro-tube/docker-compose.yml restart && echo "[+] RetroTube worker and container restarted."'
```
