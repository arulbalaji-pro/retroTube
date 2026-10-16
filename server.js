const express = require('express');
const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');

const app = express();
const PORT = 3000;

const VIDEO_DIR = process.env.VIDEO_DIR || '/media';
const THUMB_DIR = path.join(__dirname, 'public', 'thumbnails');
const EXTENSIONS = new Set(['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v']);

if (!fs.existsSync(THUMB_DIR)) {
  fs.mkdirSync(THUMB_DIR, { recursive: true });
}

app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Resilient recursive scanner
function getVideos(dir, baseDir = dir) {
  let results = [];
  if (!fs.existsSync(dir)) return results;

  let list = [];
  try {
    list = fs.readdirSync(dir, { withFileTypes: true });
  } catch (err) {
    console.warn(`[WARN] Skipping directory ${dir}: ${err.message}`);
    return results;
  }

  for (const item of list) {
    try {
      const fullPath = path.join(dir, item.name);
      if (item.isDirectory()) {
        results = results.concat(getVideos(fullPath, baseDir));
      } else {
        const ext = path.extname(item.name).toLowerCase();
        if (EXTENSIONS.has(ext)) {
          let stats = { size: 0, mtime: new Date() };
          try {
            stats = fs.statSync(fullPath);
          } catch (statErr) {
            // If stat fails (bad encoding, broken link), use fallback values instead of dying
            console.warn(`[WARN] Could not stat file ${fullPath}, using fallback date`);
          }

          const relPath = path.relative(baseDir, fullPath);
          const id = Buffer.from(relPath).toString('base64url');

          results.push({
            id,
            title: path.basename(item.name, ext),
            filename: item.name,
            relPath,
            sizeBytes: stats.size,
            mtime: stats.mtime
          });
        }
      }
    } catch (e) {
      console.warn(`[WARN] Skipping item: ${e.message}`);
    }
  }
  return results;
}

app.get('/api/videos', (req, res) => {
  try {
    const query = (req.query.q || '').trim().toLowerCase();
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 12;

    let all = getVideos(VIDEO_DIR);

    // Sort newest first
    all.sort((a, b) => new Date(b.mtime) - new Date(a.mtime));

    if (query) {
      all = all.filter(v => 
        (v.title && v.title.toLowerCase().includes(query)) ||
        (v.relPath && v.relPath.toLowerCase().includes(query))
      );
    }

    const total = all.length;
    const totalPages = Math.ceil(total / limit) || 1;
    const startIndex = (page - 1) * limit;
    const videos = all.slice(startIndex, startIndex + limit);

    res.json({
      videos,
      total,
      page,
      totalPages
    });
  } catch (err) {
    console.error('API Error:', err);
    res.status(500).json({ error: 'Internal scanning error', videos: [], total: 0, totalPages: 1 });
  }
});

app.get('/api/thumbnail/:id', (req, res) => {
  try {
    const relPath = Buffer.from(req.params.id, 'base64url').toString('utf8');
    const fullPath = path.join(VIDEO_DIR, relPath);
    const thumbName = `${req.params.id}.jpg`;
    const thumbPath = path.join(THUMB_DIR, thumbName);

    if (fs.existsSync(thumbPath)) {
      return res.sendFile(thumbPath);
    }

    if (!fs.existsSync(fullPath)) {
      return res.status(404).send('Not found');
    }

    ffmpeg(fullPath)
      .screenshots({
        timestamps: ['10%'],
        filename: thumbName,
        folder: THUMB_DIR,
        size: '320x180'
      })
      .on('end', () => res.sendFile(thumbPath))
      .on('error', () => res.status(500).send('Thumbnail error'));
  } catch (err) {
    res.status(500).send('Error');
  }
});

app.get('/api/stream/:id', (req, res) => {
  try {
    const relPath = Buffer.from(req.params.id, 'base64url').toString('utf8');
    const fullPath = path.join(VIDEO_DIR, relPath);

    if (!fs.existsSync(fullPath)) {
      return res.status(404).send('File not found');
    }

    const ext = path.extname(fullPath).toLowerCase();
    const range = req.headers.range;

    if (ext === '.mp4' || ext === '.webm') {
      let fileSize = 0;
      try {
        fileSize = fs.statSync(fullPath).size;
      } catch (e) {}

      if (range && fileSize > 0) {
        const parts = range.replace(/bytes=/, '').split('-');
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
        const chunksize = end - start + 1;
        const file = fs.createReadStream(fullPath, { start, end });
        res.writeHead(206, {
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunksize,
          'Content-Type': ext === '.mp4' ? 'video/mp4' : 'video/webm'
        });
        file.pipe(res);
      } else {
        res.writeHead(200, {
          'Content-Length': fileSize || undefined,
          'Content-Type': ext === '.mp4' ? 'video/mp4' : 'video/webm'
        });
        fs.createReadStream(fullPath).pipe(res);
      }
      return;
    }

    res.writeHead(200, {
      'Content-Type': 'video/mp4',
      'Transfer-Encoding': 'chunked'
    });

    const command = ffmpeg(fullPath)
      .format('mp4')
      .videoCodec('libx264')
      .audioCodec('aac')
      .outputOptions([
        '-movflags frag_keyframe+empty_moov+default_base_moof',
        '-preset ultrafast',
        '-crf 23',
        '-tune zerolatency'
      ])
      .on('error', () => {});

    command.pipe(res, { end: true });
  } catch (err) {
    res.status(500).send('Stream error');
  }
});




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

app.listen(PORT, '0.0.0.0', () => {
  console.log(`RetroTube live on ${PORT}`);
});
