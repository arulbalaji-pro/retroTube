with open("server.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "// --- RETROTUBE AI RATINGS & COMMENTS API" in line:
        skip = True
    if not skip:
        new_lines.append(line)
    if skip and "// -------------------------------------------" in line:
        skip = False

code = "".join(new_lines)

bridge_endpoint = """
// --- RETROTUBE AI RATINGS & COMMENTS API (Native Fetch Bridge) ---
app.get('/api/comments', async (req, res) => {
  const vidId = req.query.id || 'default';
  const vidTitle = req.query.title || vidId;
  try {
    const response = await fetch(`http://host.docker.internal:5055/comments?id=${encodeURIComponent(vidId)}&title=${encodeURIComponent(vidTitle)}`);
    const data = await response.json();
    res.json(data);
  } catch (err) {
    res.json({ comments: [] });
  }
});
// -------------------------------------------
"""

code = code.replace("app.listen(", bridge_endpoint + "\napp.listen(")

with open("server.js", "w", encoding="utf-8") as f:
    f.write(code)
print("[+] server.js updated: No sqlite3 npm dependency needed!")
