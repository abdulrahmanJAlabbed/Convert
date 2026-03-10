"""
Transcription Dashboard
=======================
Run this alongside transcribe.py to see live progress.

Usage:
  .venv\\Scripts\\activate
  python dashboard.py
  Open http://localhost:5000
"""

import json
from pathlib import Path
from flask import Flask, Response

app = Flask(__name__)
ROOT = Path(__file__).parent
STATUS_FILE = ROOT / "status.json"
INPUT_DIR   = ROOT / "input"
OUTPUT_DIR  = ROOT / "output"


@app.route("/")
def index():
    return Response(HTML, content_type="text/html")


@app.route("/api/status")
def api_status():
    # Build a combined status with file lists
    status = {"state": "waiting", "videos": {}, "input_files": [], "output_files": []}
    if STATUS_FILE.exists():
        status.update(json.loads(STATUS_FILE.read_text(encoding="utf-8")))
    # Always scan real files
    if INPUT_DIR.exists():
        status["input_files"] = [
            {"name": f.name, "size_mb": round(f.stat().st_size / 1e6, 1)}
            for f in sorted(INPUT_DIR.glob("*.mp4"))
        ]
    if OUTPUT_DIR.exists():
        status["output_files"] = [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in sorted(OUTPUT_DIR.iterdir()) if f.suffix in (".txt", ".srt")
        ]
    return Response(json.dumps(status, ensure_ascii=False), content_type="application/json")


@app.route("/api/file/<path:name>")
def api_file(name):
    p = OUTPUT_DIR / name
    if p.exists() and p.suffix in (".txt", ".srt"):
        return Response(p.read_text(encoding="utf-8"), content_type="text/plain; charset=utf-8")
    return Response("Not found", status=404)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transcription Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #06060b;
    --surface: #0e0e16;
    --surface2: #15151f;
    --surface3: #1c1c2a;
    --border: #252538;
    --border2: #333350;
    --text: #e8e8f0;
    --text2: #7a7a95;
    --text3: #55556a;
    --accent: #7c6af0;
    --accent2: #b0a4ff;
    --green: #34d399;
    --green-dim: rgba(52,211,153,0.12);
    --orange: #fbbf24;
    --orange-dim: rgba(251,191,36,0.12);
    --blue: #60a5fa;
    --blue-dim: rgba(96,165,250,0.12);
    --red: #f87171;
    --r: 14px;
    --r-sm: 10px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* Layout */
  .shell { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }

  /* Header */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
    flex-wrap: wrap;
    gap: 1rem;
  }
  .header-left h1 {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #fff 30%, var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-left p { color: var(--text2); font-size: 0.85rem; margin-top: 0.25rem; }

  /* Stat pills */
  .pills { display: flex; gap: 0.6rem; flex-wrap: wrap; }
  .pill {
    display: flex; align-items: center; gap: 0.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 0.5rem 1rem;
    font-size: 0.8rem;
  }
  .pill .dot {
    width: 8px; height: 8px; border-radius: 50%;
  }
  .dot.green { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .dot.orange { background: var(--orange); box-shadow: 0 0 8px var(--orange); animation: blink 1.2s ease-in-out infinite; }
  .dot.gray { background: var(--text3); }
  .dot.blue { background: var(--blue); box-shadow: 0 0 8px var(--blue); }
  @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.3; } }

  /* Two-column layout */
  .columns { display: grid; grid-template-columns: 320px 1fr; gap: 1.5rem; }
  @media (max-width: 800px) { .columns { grid-template-columns: 1fr; } }

  /* Sidebar — Input Files */
  .sidebar { display: flex; flex-direction: column; gap: 1rem; }
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .panel-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text2);
    padding: 1rem 1.2rem 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .panel-title .count {
    background: var(--surface3);
    padding: 0.15rem 0.5rem;
    border-radius: 100px;
    font-size: 0.65rem;
    color: var(--text3);
  }

  /* File row */
  .file-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.65rem 1.2rem;
    border-top: 1px solid var(--border);
    font-size: 0.82rem;
    transition: background 0.15s;
  }
  .file-row:hover { background: var(--surface2); }
  .file-row .fname { font-weight: 500; }
  .file-row .fmeta { color: var(--text3); font-size: 0.75rem; }
  .file-row .icon-sm {
    width: 28px; height: 28px; border-radius: 7px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; margin-right: 0.6rem; flex-shrink: 0;
  }
  .file-row .left { display: flex; align-items: center; }
  .icon-video { background: var(--blue-dim); color: var(--blue); }
  .icon-txt { background: var(--green-dim); color: var(--green); }
  .icon-srt { background: var(--orange-dim); color: var(--orange); }

  /* Main — Transcription Cards */
  .main { display: flex; flex-direction: column; gap: 1rem; }

  .vcard {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    transition: border-color 0.25s, box-shadow 0.25s;
  }
  .vcard.active {
    border-color: var(--accent);
    box-shadow: 0 0 30px rgba(124,106,240,0.08);
  }
  .vcard.done { border-color: rgba(52,211,153,0.3); }

  .vcard-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.2rem;
    cursor: pointer;
    user-select: none;
  }
  .vcard-head .left { display: flex; align-items: center; gap: 0.8rem; }
  .vcard-head .num {
    width: 32px; height: 32px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.85rem;
  }
  .num.waiting { background: var(--surface3); color: var(--text3); }
  .num.transcribing { background: rgba(124,106,240,0.15); color: var(--accent2); animation: blink 1.5s ease-in-out infinite; }
  .num.done { background: var(--green-dim); color: var(--green); }

  .vcard-head .info .name { font-weight: 600; font-size: 0.9rem; }
  .vcard-head .info .meta { font-size: 0.78rem; color: var(--text2); margin-top: 1px; }

  .badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.3rem 0.75rem;
    border-radius: 100px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .badge.waiting { background: var(--surface3); color: var(--text3); }
  .badge.transcribing { background: rgba(124,106,240,0.15); color: var(--accent2); }
  .badge.done { background: var(--green-dim); color: var(--green); }

  /* Progress */
  .vcard-progress {
    height: 3px;
    background: var(--surface3);
    margin: 0 1.2rem 0.5rem;
    border-radius: 2px;
    overflow: hidden;
  }
  .vcard-progress .fill {
    height: 100%;
    border-radius: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 0.5s ease;
  }

  /* Transcript body */
  .vcard-body {
    display: none;
    border-top: 1px solid var(--border);
    max-height: 350px;
    overflow-y: auto;
  }
  .vcard-body.open { display: block; }

  .seg {
    display: flex;
    gap: 0.75rem;
    padding: 0.55rem 1.2rem;
    font-size: 0.82rem;
    border-bottom: 1px solid rgba(37,37,56,0.6);
    transition: background 0.12s;
  }
  .seg:hover { background: var(--surface2); }
  .seg:last-child { border-bottom: none; }
  .seg-ts {
    color: var(--accent2);
    font-family: 'Courier New', monospace;
    font-size: 0.72rem;
    white-space: nowrap;
    padding-top: 2px;
    flex-shrink: 0;
    opacity: 0.8;
  }
  .seg-txt { line-height: 1.55; color: var(--text); }
  .empty-body {
    padding: 1.5rem;
    text-align: center;
    color: var(--text3);
    font-size: 0.82rem;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--border2); }
</style>
</head>
<body>
<div class="shell">

  <div class="header">
    <div class="header-left">
      <h1>Transcription Dashboard</h1>
      <p id="subtitle">Waiting for transcription to start...</p>
    </div>
    <div class="pills" id="pills"></div>
  </div>

  <div class="columns">
    <div class="sidebar">
      <div class="panel" id="inputPanel">
        <div class="panel-title">Input Videos <span class="count" id="inputCount">0</span></div>
      </div>
      <div class="panel" id="outputPanel">
        <div class="panel-title">Output Files <span class="count" id="outputCount">0</span></div>
      </div>
    </div>
    <div class="main" id="main"></div>
  </div>

</div>

<script>
let openCards = new Set();
let lastData = null;
function toggle(n) { openCards.has(n) ? openCards.delete(n) : openCards.add(n); if(lastData) render(lastData); }
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

function render(d) {
  lastData = d;
  const vids = d.videos || {};
  const total = d.total_videos || 0;
  const done = Object.values(vids).filter(v=>v.status==='done').length;
  const segs = Object.values(vids).reduce((s,v)=>s+(v.segments||[]).length,0);
  const dev = (d.device||'?').toUpperCase();

  // Subtitle
  const sub = document.getElementById('subtitle');
  if (d.state==='loading_model') sub.textContent = `Loading ${d.model} on ${dev}...`;
  else if (d.state==='transcribing') sub.textContent = `Transcribing with ${d.model} on ${dev}`;
  else if (d.state==='done') sub.textContent = `Completed in ${d.total_time||'?'}`;
  else sub.textContent = 'Waiting for transcription to start...';

  // Pills
  const dotCls = d.state==='done'?'green':d.state==='transcribing'?'orange':'gray';
  document.getElementById('pills').innerHTML = `
    <div class="pill"><span class="dot ${dotCls}"></span>${d.state||'waiting'}</div>
    <div class="pill"><span class="dot ${dev==='CUDA'?'blue':'gray'}"></span>${dev}</div>
    <div class="pill">${done}/${total} done</div>
    <div class="pill">${segs} segments</div>
  `;

  // Input panel
  const inp = d.input_files || [];
  document.getElementById('inputCount').textContent = inp.length;
  let ih = '';
  for (const f of inp) {
    const st = vids[f.name]?.status || 'waiting';
    ih += `<div class="file-row"><div class="left"><div class="icon-sm icon-video">&#9654;</div><span class="fname">${esc(f.name)}</span></div><span class="fmeta">${f.size_mb} MB</span></div>`;
  }
  document.getElementById('inputPanel').innerHTML = `<div class="panel-title">Input Videos <span class="count">${inp.length}</span></div>${ih || '<div class="empty-body">No videos in input/</div>'}`;

  // Output panel
  const outp = d.output_files || [];
  document.getElementById('outputCount').textContent = outp.length;
  let oh = '';
  for (const f of outp) {
    const ext = f.name.split('.').pop();
    const cls = ext==='srt' ? 'icon-srt' : 'icon-txt';
    const sym = ext==='srt' ? 'SRT' : 'TXT';
    oh += `<div class="file-row"><div class="left"><div class="icon-sm ${cls}">${sym}</div><span class="fname">${esc(f.name)}</span></div><span class="fmeta">${f.size_kb} KB</span></div>`;
  }
  document.getElementById('outputPanel').innerHTML = `<div class="panel-title">Output Files <span class="count">${outp.length}</span></div>${oh || '<div class="empty-body">No outputs yet</div>'}`;

  // Main cards
  const list = d.video_list || [];
  let mh = '';
  for (let idx=0; idx<list.length; idx++) {
    const name = list[idx];
    const v = vids[name] || {};
    const st = v.status || 'waiting';
    const segs = v.segments || [];
    const isOpen = openCards.has(name);

    let meta = [];
    if (v.language) meta.push(v.language.toUpperCase());
    if (v.duration) meta.push(`${v.duration}s`);
    if (v.elapsed) meta.push(`${(v.elapsed/60).toFixed(1)} min`);
    if (v.speed) meta.push(v.speed + ' speed');

    let pct = 0;
    if (st==='done') pct = 100;
    else if (v.duration && segs.length) {
      const last = segs[segs.length-1];
      if (last?.end) {
        const p = last.end.split(/[:,]/);
        const sec = +p[0]*3600 + +p[1]*60 + +p[2];
        pct = Math.min(99, Math.round(sec / v.duration * 100));
      }
    }

    const sym = st==='done' ? '&#10003;' : st==='transcribing' ? '&#9654;' : (idx+1);

    mh += `
    <div class="vcard ${st==='transcribing'?'active':''} ${st==='done'?'done':''}">
      <div class="vcard-head" onclick="toggle('${name}')">
        <div class="left">
          <div class="num ${st}">${sym}</div>
          <div class="info">
            <div class="name">${esc(name)}</div>
            <div class="meta">${meta.join(' &middot; ') || 'Queued'}</div>
          </div>
        </div>
        <span class="badge ${st}">${st}</span>
      </div>
      ${st!=='waiting'?`<div class="vcard-progress"><div class="fill" style="width:${pct}%"></div></div>`:''}
      <div class="vcard-body ${isOpen?'open':''}">
        ${segs.length ? segs.map(s=>`<div class="seg"><span class="seg-ts">${s.start}</span><span class="seg-txt">${esc(s.text)}</span></div>`).join('') : `<div class="empty-body">${st==='waiting'?'Queued':'Processing...'}</div>`}
      </div>
    </div>`;
  }
  document.getElementById('main').innerHTML = mh || '<div class="empty-body">No videos found. Place .mp4 files in input/ folder.</div>';
}

async function poll() {
  try { const r = await fetch('/api/status'); render(await r.json()); } catch(e) {}
  setTimeout(poll, 2000);
}
poll();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("\n  Dashboard: http://localhost:5000")
    print("  Open in browser to see transcription progress.\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
