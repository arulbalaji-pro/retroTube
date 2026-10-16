import os, glob

# 1. Update public/index.html
index_path = "public/index.html"
if os.path.exists(index_path):
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    rt_ui = """
      <!-- RetroTube Star Ratings & Comments -->
      <style>
        .rt-rating-row {
          margin-top: 10px;
          padding: 8px 0;
          border-top: 1px solid #d3d3d3;
          border-bottom: 1px solid #d3d3d3;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-family: Arial, sans-serif;
          font-size: 12px;
          color: #333;
        }
        .rt-stars {
          color: #cc9900;
          font-size: 15px;
          letter-spacing: 2px;
        }
        .rt-comments-section {
          margin-top: 15px;
          font-family: Arial, sans-serif;
        }
        .rt-comments-header {
          font-weight: bold;
          font-size: 13px;
          border-bottom: 2px solid #555;
          padding-bottom: 4px;
          margin-bottom: 10px;
          color: #222;
        }
        .rt-comment-item {
          display: flex;
          gap: 10px;
          padding: 8px 0;
          border-bottom: 1px solid #eee;
          font-size: 12px;
          line-height: 1.4;
        }
        .rt-avatar {
          width: 32px;
          height: 32px;
          background: #e2e2e2;
          border: 1px solid #ccc;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 15px;
          border-radius: 2px;
          flex-shrink: 0;
        }
        .rt-username {
          color: #0033cc;
          font-weight: bold;
        }
        .rt-comment-stars {
          color: #d19200;
          font-size: 11px;
          margin-left: 6px;
        }
        .rt-comment-text {
          margin-top: 2px;
          color: #222;
        }
      </style>

      <div class="rt-rating-row">
        <div>
          <strong>Rating:</strong>
          <span class="rt-stars" id="rtStarsDisplay">★★★★☆</span>
          <span id="rtRatingInfo" style="color:#666; font-size:11px;">(4.5 avg · calculating...)</span>
        </div>
      </div>

      <div class="rt-comments-section">
        <div class="rt-comments-header">
          <span id="rtCommentTitle">Comments</span>
        </div>
        <div id="rtCommentsContainer">
          <div style="color:#888; font-size:11px; padding:6px 0;">Loading comments...</div>
        </div>
      </div>
    """

    rt_js = """
    let currentRtPoll = null;
    async function loadRetroTubeComments(vidId, vidTitle) {
      if (currentRtPoll) clearInterval(currentRtPoll);

      async function fetchComments() {
        try {
          const res = await fetch('/api/comments?id=' + encodeURIComponent(vidId) + '&title=' + encodeURIComponent(vidTitle || vidId));
          if (!res.ok) return;
          const data = await res.json();
          const comments = data.comments || [];

          if (comments.length > 0) {
            const sum = comments.reduce((acc, c) => acc + (c.stars || 5), 0);
            const avg = (sum / comments.length).toFixed(1);
            const round = Math.round(avg);
            document.getElementById("rtStarsDisplay").textContent = "★".repeat(round) + "☆".repeat(5 - round);
            document.getElementById("rtRatingInfo").textContent = `(${avg} avg · ${comments.length} ratings)`;
            document.getElementById("rtCommentTitle").textContent = `Comments (${comments.length})`;

            let html = "";
            comments.forEach(c => {
              const stars = "★".repeat(c.stars || 5) + "☆".repeat(5 - (c.stars || 5));
              html += `
                <div class="rt-comment-item">
                  <div class="rt-avatar">👤</div>
                  <div style="flex:1;">
                    <div>
                      <span class="rt-username">${c.username}</span>
                      <span class="rt-comment-stars">${stars}</span>
                    </div>
                    <div class="rt-comment-text">${c.comment}</div>
                  </div>
                </div>
              `;
            });
            document.getElementById("rtCommentsContainer").innerHTML = html;
          } else {
            document.getElementById("rtStarsDisplay").textContent = "★★★★☆";
            document.getElementById("rtRatingInfo").textContent = "(Awaiting ratings)";
            document.getElementById("rtCommentTitle").textContent = "Comments (0)";
            document.getElementById("rtCommentsContainer").innerHTML = '<div style="color:#888; font-size:11px; padding:6px 0;">No comments yet.</div>';
          }
        } catch (e) {
          console.error("Error fetching comments:", e);
        }
      }

      fetchComments();
      currentRtPoll = setInterval(fetchComments, 4000);
    }
    """

    if "rt-rating-row" not in html:
        hook = "dateEl.textContent = dateStr ? `Added on ${dateStr}` : '';"
        if hook in html:
            html = html.replace(hook, hook + "\n      loadRetroTubeComments(video.id || video.title || 'default', video.title || '');")
        
        idx = html.find("dateEl")
        if idx != -1:
            close_div = html.find("</div>", idx)
            if close_div != -1:
                html = html[:close_div+6] + "\n" + rt_ui + "\n" + html[close_div+6:]

        if "</script>" in html:
            html = html.replace("</script>", rt_js + "\n</script>", 1)

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
        print("[+] Patched public/index.html with Ratings and Comments UI")
    else:
        print("[=] public/index.html already patched.")

# 2. Update Server Script
server_candidates = ["server.js", "app.js", "index.js", "src/server.js"]
for srv in server_candidates:
    if os.path.exists(srv):
        with open(srv, "r", encoding="utf-8") as f:
            srv_code = f.read()

        endpoint_code = """
// --- RETROTUBE AI RATINGS & COMMENTS API ---
const sqlite3 = require('sqlite3').verbose();
const rtDb = new sqlite3.Database('./retrotube.db');

app.get('/api/comments', (req, res) => {
  const vidId = req.query.id || 'default';
  const vidTitle = req.query.title || vidId;

  rtDb.get("SELECT COUNT(*) as count FROM comments WHERE video_id = ?", [vidId], (err, row) => {
    if (!err && row && row.count === 0) {
      rtDb.get("SELECT COUNT(*) as scount FROM scheduled_tasks WHERE video_id = ?", [vidId], (sErr, sRow) => {
        if (!sErr && sRow && sRow.scount === 0) {
          const total = Math.floor(Math.random() * 5) + 4;
          const half = Math.ceil(total / 2);
          const types = Array(half).fill('support');
          const others = ['critic', 'curious', 'toxic'];
          while (types.length < total) {
            types.push(others[Math.floor(Math.random() * others.length)]);
          }
          types.sort(() => Math.random() - 0.5);

          const names = {
            support: ['RetroFan', 'Aarav', 'PixelSamurai', 'NostalgiaLover', 'CyberKnight', 'Maya'],
            critic: ['TechReviewer', 'FilmSnob99', 'LogicSeeker', 'CynicOne'],
            curious: ['CuriousCat', 'VintageHunter', 'Anon2008', 'ExplorerX'],
            toxic: ['EdgeLord42', 'HaterBot', 'RageBaiter']
          };

          let now = Date.now() / 1000;
          types.forEach(t => {
            now += Math.floor(Math.random() * 25) + 10;
            const uname = names[t][Math.floor(Math.random() * names[t].length)];
            const stars = t === 'support' ? (Math.random() > 0.5 ? 5 : 4) : (t === 'curious' ? 3 : (Math.random() > 0.5 ? 2 : 1));
            rtDb.run(
              "INSERT INTO scheduled_tasks (video_id, username, ai_type, stars, prompt, scheduled_time, executed) VALUES (?, ?, ?, ?, ?, ?, 0)",
              [vidId, uname, t, stars, vidTitle, now]
            );
          });
        }
      });
    }
  });

  rtDb.all("SELECT username, ai_type, stars, comment, created_at FROM comments WHERE video_id = ? ORDER BY id ASC", [vidId], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ comments: rows || [] });
  });
});
// -------------------------------------------
"""
        if "/api/comments" not in srv_code:
            if "app.listen(" in srv_code:
                srv_code = srv_code.replace("app.listen(", endpoint_code + "\napp.listen(")
                with open(srv, "w", encoding="utf-8") as f:
                    f.write(srv_code)
                print(f"[+] Injected /api/comments endpoint into {srv}")
        break
