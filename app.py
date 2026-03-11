"""
Transcripe — All-in-One Transcription Dashboard
=================================================
Single app: launches the dashboard AND runs transcription.
Usage:  python app.py
Open:   http://localhost:5000
"""

import sys, io, os, time, json, threading
from pathlib import Path

# UTF-8 console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── CUDA DLL fix ─────────────────────────────────────────────────────────────
import site
for sp in site.getsitepackages():
    nvidia_dir = Path(sp) / "nvidia"
    if nvidia_dir.is_dir():
        for pkg in nvidia_dir.iterdir():
            dll_dir = pkg / "bin"
            if dll_dir.is_dir():
                os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(dll_dir))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# ─────────────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).parent
INPUT_DIR = ROOT / "input"
OUT_DIR   = ROOT / "output"
TXT_DIR   = OUT_DIR / "txt"
SRT_DIR   = OUT_DIR / "srt"
CACHE_DIR = ROOT / "model_cache"
CFG_FILE  = ROOT / "config.json"

for d in (INPUT_DIR, OUT_DIR, TXT_DIR, SRT_DIR, CACHE_DIR):
    d.mkdir(exist_ok=True)
os.environ["HF_HOME"] = str(CACHE_DIR)

from flask import Flask, Response, request, send_file
app_flask = Flask(__name__)

# ── Shared state ─────────────────────────────────────────────────────────────
state = {
    "status": "idle",        # idle | loading | transcribing | done | error
    "device": "cuda",
    "model": "large-v3",
    "total_videos": 0,
    "completed": 0,
    "current_video": None,
    "current_idx": 0,
    "videos": {},
    "video_list": [],
    "error": None,
    "total_time": None,
}
state_lock = threading.Lock()
transcription_thread = None


def load_config():
    defaults = {"model": "large-v3", "device": "cuda", "compute": "float16",
                "language": None, "beam_size": 5}
    if CFG_FILE.exists():
        try:
            saved = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            defaults.update(saved)
        except: pass
    return defaults

def save_config(cfg):
    CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def fmt_ts(s):
    ms = int((s % 1) * 1000)
    return f"{int(s)//3600:02d}:{(int(s)//60)%60:02d}:{int(s)%60:02d},{ms:03d}"


def run_transcription():
    global state
    cfg = load_config()

    with state_lock:
        state["status"] = "loading"
        state["error"] = None

    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(cfg["model"], device=cfg["device"],
                             compute_type=cfg["compute"],
                             download_root=str(CACHE_DIR))
        with state_lock:
            state["device"] = cfg["device"]
    except Exception as e:
        try:
            model = WhisperModel(cfg["model"], device="cpu", compute_type="int8",
                                 download_root=str(CACHE_DIR))
            with state_lock:
                state["device"] = "cpu"
        except Exception as e2:
            with state_lock:
                state["status"] = "error"
                state["error"] = str(e2)
            return

    videos = sorted(INPUT_DIR.glob("*.mp4"))
    with state_lock:
        state["status"] = "transcribing"
        state["model"] = cfg["model"]
        state["total_videos"] = len(videos)
        state["completed"] = 0
        state["video_list"] = [v.name for v in videos]
        state["videos"] = {}

    if not videos:
        with state_lock:
            state["status"] = "error"
            state["error"] = "No .mp4 files found in input/"
        return

    total_t = time.time()
    lang = cfg.get("language") or None
    beam = cfg.get("beam_size", 5)

    for idx, video in enumerate(videos, 1):
        name = video.name
        week = f"Transcript_Week_{idx}"

        with state_lock:
            state["current_video"] = name
            state["current_idx"] = idx
            state["videos"][name] = {
                "status": "transcribing",
                "output_name": week,
                "segments": [],
                "language": None,
                "duration": None,
                "elapsed": None,
            }

        txt_path = TXT_DIR / f"{week}.txt"
        srt_path = SRT_DIR / f"{week}.srt"
        t0 = time.time()

        try:
            segments, info = model.transcribe(
                str(video), beam_size=beam, language=lang,
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
            )

            with state_lock:
                state["videos"][name]["language"] = info.language
                state["videos"][name]["duration"] = round(info.duration, 1)

            with open(txt_path, "w", encoding="utf-8") as tf, \
                 open(srt_path, "w", encoding="utf-8") as sf:
                for i, seg in enumerate(segments, 1):
                    text = seg.text.strip()
                    st_ts, en_ts = fmt_ts(seg.start), fmt_ts(seg.end)
                    tf.write(text + "\n"); tf.flush()
                    sf.write(f"{i}\n{st_ts} --> {en_ts}\n{text}\n\n"); sf.flush()

                    with state_lock:
                        state["videos"][name]["segments"].append(
                            {"id": i, "start": st_ts, "end": en_ts, "text": text})
                        state["videos"][name]["elapsed"] = round(time.time() - t0, 1)

            elapsed = time.time() - t0
            speed = info.duration / elapsed if elapsed else 0
            with state_lock:
                state["videos"][name]["status"] = "done"
                state["videos"][name]["elapsed"] = round(elapsed, 1)
                state["videos"][name]["speed"] = f"{speed:.1f}x"
                state["videos"][name]["txt"] = f"output/txt/{week}.txt"
                state["videos"][name]["srt"] = f"output/srt/{week}.srt"
                state["completed"] = idx

        except Exception as e:
            with state_lock:
                state["videos"][name]["status"] = "error"
                state["videos"][name]["error"] = str(e)

    with state_lock:
        state["status"] = "done"
        state["total_time"] = f"{(time.time()-total_t)/60:.1f} min"
        state["current_video"] = None


# ── API Routes ────────────────────────────────────────────────────────────────

@app_flask.route("/")
def index():
    return Response(HTML, content_type="text/html")

@app_flask.route("/api/status")
def api_status():
    with state_lock:
        data = dict(state)
        # Add live file info
        data["input_files"] = [
            {"name": f.name, "size_mb": round(f.stat().st_size / 1e6, 1)}
            for f in sorted(INPUT_DIR.glob("*.mp4"))
        ] if INPUT_DIR.exists() else []
        data["txt_files"] = [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in sorted(TXT_DIR.glob("*.txt"))
        ] if TXT_DIR.exists() else []
        data["srt_files"] = [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in sorted(SRT_DIR.glob("*.srt"))
        ] if SRT_DIR.exists() else []
    return Response(json.dumps(data, ensure_ascii=False), content_type="application/json")

@app_flask.route("/api/start", methods=["POST"])
def api_start():
    global transcription_thread
    if transcription_thread and transcription_thread.is_alive():
        return Response('{"error":"Already running"}', status=409, content_type="application/json")
    transcription_thread = threading.Thread(target=run_transcription, daemon=True)
    transcription_thread.start()
    return Response('{"ok":true}', content_type="application/json")

@app_flask.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        cfg = request.get_json()
        save_config(cfg)
        return Response('{"ok":true}', content_type="application/json")
    return Response(json.dumps(load_config()), content_type="application/json")

@app_flask.route("/api/transcript/<folder>/<name>")
def api_transcript(folder, name):
    d = TXT_DIR if folder == "txt" else SRT_DIR if folder == "srt" else None
    if d:
        p = d / name
        if p.exists():
            return Response(p.read_text(encoding="utf-8"), content_type="text/plain; charset=utf-8")
    return Response("Not found", status=404)

@app_flask.route("/api/transcript/<folder>/<name>", methods=["PUT"])
def api_save_transcript(folder, name):
    d = TXT_DIR if folder == "txt" else SRT_DIR if folder == "srt" else None
    if d:
        p = d / name
        content = request.get_data(as_text=True)
        p.write_text(content, encoding="utf-8")
        return Response('{"ok":true}', content_type="application/json")
    return Response("Not found", status=404)

@app_flask.route("/api/download/<folder>/<name>")
def api_download(folder, name):
    d = TXT_DIR if folder == "txt" else SRT_DIR if folder == "srt" else None
    if d:
        p = d / name
        if p.exists():
            return send_file(str(p), as_attachment=True)
    return Response("Not found", status=404)


# ── HTML Dashboard ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transcripe</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#06060b; --s1:#0d0d15; --s2:#13131e; --s3:#1a1a28;
  --border:#222236; --b2:#2e2e48;
  --t1:#eaeaf2; --t2:#8585a0; --t3:#5a5a72;
  --ac:#7c6af0; --ac2:#b0a4ff;
  --grn:#34d399; --grn-d:rgba(52,211,153,.12);
  --orn:#fbbf24; --orn-d:rgba(251,191,36,.12);
  --blu:#60a5fa; --blu-d:rgba(96,165,250,.12);
  --pur-d:rgba(124,106,240,.12);
  --red:#f87171; --red-d:rgba(248,113,113,.12);
  --r:14px; --r2:10px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;}
.shell{max-width:1340px;margin:0 auto;padding:1.5rem;}

/* Header */
.hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:1rem;}
.hdr h1{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;background:linear-gradient(135deg,#fff 30%,var(--ac2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hdr .sub{color:var(--t2);font-size:.82rem;margin-top:.15rem;}
.pills{display:flex;gap:.4rem;flex-wrap:wrap;}
.pill{display:flex;align-items:center;gap:.4rem;background:var(--s1);border:1px solid var(--border);border-radius:100px;padding:.35rem .8rem;font-size:.72rem;font-weight:500;}
.dot{width:7px;height:7px;border-radius:50%;}
.dot.grn{background:var(--grn);box-shadow:0 0 8px var(--grn);}
.dot.orn{background:var(--orn);box-shadow:0 0 8px var(--orn);animation:blink 1.2s infinite;}
.dot.gry{background:var(--t3);}
.dot.blu{background:var(--blu);box-shadow:0 0 6px var(--blu);}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}

/* Toolbar */
.toolbar{display:flex;gap:.6rem;margin-bottom:1.5rem;flex-wrap:wrap;align-items:center;}
.btn{padding:.55rem 1.1rem;border-radius:var(--r2);font-size:.78rem;font-weight:600;border:none;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:.4rem;}
.btn-start{background:var(--grn);color:#000;} .btn-start:hover{background:#2bc489;transform:translateY(-1px);}
.btn-start:disabled{opacity:.4;cursor:not-allowed;transform:none;}
.btn-settings{background:var(--s2);color:var(--t2);border:1px solid var(--border);} .btn-settings:hover{border-color:var(--ac);color:var(--t1);}

/* Layout */
.layout{display:grid;grid-template-columns:240px 1fr 240px;gap:1rem;}
@media(max-width:1000px){.layout{grid-template-columns:1fr;}}

/* Panel */
.pnl{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;}
.pnl-hd{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--t2);padding:.8rem .9rem .45rem;display:flex;align-items:center;gap:.4rem;}
.pnl-hd .cnt{background:var(--s3);padding:.1rem .4rem;border-radius:100px;font-size:.58rem;color:var(--t3);}
.fr{display:flex;align-items:center;justify-content:space-between;padding:.45rem .9rem;border-top:1px solid var(--border);font-size:.75rem;transition:background .12s;cursor:default;}
.fr:hover{background:var(--s2);}
.fr .l{display:flex;align-items:center;gap:.4rem;}
.ico{width:24px;height:24px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:700;flex-shrink:0;}
.ico-mp4{background:var(--blu-d);color:var(--blu);} .ico-txt{background:var(--grn-d);color:var(--grn);} .ico-srt{background:var(--orn-d);color:var(--orn);}
.fr .fn{font-weight:500;font-size:.73rem;} .fr .fm{color:var(--t3);font-size:.65rem;}
.empty{padding:1rem;text-align:center;color:var(--t3);font-size:.75rem;}
.fr .dl-btn{background:none;border:none;color:var(--t3);cursor:pointer;font-size:.7rem;padding:2px 6px;border-radius:4px;transition:all .15s;}
.fr .dl-btn:hover{background:var(--s3);color:var(--ac2);}

/* Cards */
.cards{display:flex;flex-direction:column;gap:.8rem;}
.vc{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;transition:border-color .25s,box-shadow .25s;}
.vc.active{border-color:var(--ac);box-shadow:0 0 20px rgba(124,106,240,.08);}
.vc.done{border-color:rgba(52,211,153,.25);}
.vc.err{border-color:rgba(248,113,113,.3);}
.vh{display:flex;align-items:center;justify-content:space-between;padding:.8rem 1rem;cursor:pointer;user-select:none;}
.vh .l{display:flex;align-items:center;gap:.65rem;}
.vh .num{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.75rem;}
.num.waiting{background:var(--s3);color:var(--t3);} .num.transcribing{background:var(--pur-d);color:var(--ac2);animation:blink 1.5s infinite;} .num.done{background:var(--grn-d);color:var(--grn);} .num.error{background:var(--red-d);color:var(--red);}
.vh .vn{font-weight:600;font-size:.83rem;}.vh .vm{font-size:.72rem;color:var(--t2);margin-top:1px;}.vh .vo{font-size:.67rem;color:var(--ac2);margin-top:1px;}
.bdg{font-size:.58rem;font-weight:700;padding:.22rem .55rem;border-radius:100px;text-transform:uppercase;letter-spacing:.04em;}
.bdg.waiting{background:var(--s3);color:var(--t3);} .bdg.transcribing{background:var(--pur-d);color:var(--ac2);} .bdg.done{background:var(--grn-d);color:var(--grn);} .bdg.error{background:var(--red-d);color:var(--red);}
.vp{height:3px;background:var(--s3);margin:0 1rem .35rem;border-radius:2px;overflow:hidden;}
.vp .fill{height:100%;border-radius:2px;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .5s ease;}
.vb{display:none;border-top:1px solid var(--border);max-height:280px;overflow-y:auto;}
.vb.open{display:block;}
.seg{display:flex;gap:.65rem;padding:.45rem 1rem;font-size:.76rem;border-bottom:1px solid rgba(34,34,54,.5);transition:background .1s;}
.seg:hover{background:var(--s2);}.seg:last-child{border-bottom:none;}
.seg-ts{color:var(--ac2);font-family:'Courier New',monospace;font-size:.67rem;white-space:nowrap;padding-top:2px;flex-shrink:0;opacity:.75;}
.seg-tx{line-height:1.5;}
/* View/Edit buttons in card */
.vactions{display:flex;gap:.4rem;padding:.4rem 1rem;border-top:1px solid var(--border);background:var(--s2);}
.vactions .abtn{font-size:.65rem;padding:.25rem .6rem;border-radius:6px;border:1px solid var(--border);background:var(--s3);color:var(--t2);cursor:pointer;transition:all .15s;}
.vactions .abtn:hover{border-color:var(--ac);color:var(--t1);}

/* Modal */
.modal-bg{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:100;justify-content:center;align-items:center;backdrop-filter:blur(4px);}
.modal-bg.show{display:flex;}
.modal{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);width:90%;max-width:700px;max-height:85vh;overflow:hidden;display:flex;flex-direction:column;}
.modal-hd{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.2rem;border-bottom:1px solid var(--border);}
.modal-hd h2{font-size:1rem;font-weight:700;}
.modal-hd .close{background:none;border:none;color:var(--t3);cursor:pointer;font-size:1.2rem;padding:4px;} .modal-hd .close:hover{color:var(--t1);}
.modal-body{padding:1.2rem;overflow-y:auto;flex:1;}
.modal-body textarea{width:100%;min-height:300px;background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);color:var(--t1);font-family:'Courier New',monospace;font-size:.8rem;padding:.8rem;resize:vertical;line-height:1.6;}
.modal-body textarea:focus{outline:none;border-color:var(--ac);}
.modal-ft{display:flex;justify-content:flex-end;gap:.5rem;padding:.8rem 1.2rem;border-top:1px solid var(--border);}
.modal-ft .btn-save{background:var(--ac);color:#fff;padding:.45rem 1rem;border:none;border-radius:var(--r2);font-size:.78rem;font-weight:600;cursor:pointer;} .modal-ft .btn-save:hover{background:var(--ac2);}
.modal-ft .btn-cancel{background:var(--s3);color:var(--t2);padding:.45rem 1rem;border:1px solid var(--border);border-radius:var(--r2);font-size:.78rem;cursor:pointer;} .modal-ft .btn-cancel:hover{color:var(--t1);}

/* Settings modal fields */
.field{margin-bottom:1rem;}
.field label{display:block;font-size:.72rem;font-weight:600;color:var(--t2);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem;}
.field select,.field input{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);color:var(--t1);padding:.5rem .7rem;font-size:.82rem;}
.field select:focus,.field input:focus{outline:none;border-color:var(--ac);}

::-webkit-scrollbar{width:5px;}::-webkit-scrollbar-track{background:transparent;}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
</style>
</head>
<body>
<div class="shell">
  <div class="hdr">
    <div><h1>Transcripe</h1><p class="sub" id="sub">Ready</p></div>
    <div class="pills" id="pills"></div>
  </div>
  <div class="toolbar" id="toolbar">
    <button class="btn btn-start" id="startBtn" onclick="startTranscription()">&#9654; Start Transcription</button>
    <button class="btn btn-settings" onclick="openSettings()">&#9881; Settings</button>
  </div>
  <div class="layout">
    <div id="leftCol"></div>
    <div class="cards" id="cards"></div>
    <div id="rightCol"></div>
  </div>
</div>

<!-- Edit Modal -->
<div class="modal-bg" id="editModal">
  <div class="modal">
    <div class="modal-hd"><h2 id="editTitle">Edit Transcript</h2><button class="close" onclick="closeEdit()">&times;</button></div>
    <div class="modal-body"><textarea id="editArea"></textarea></div>
    <div class="modal-ft"><button class="btn-cancel" onclick="closeEdit()">Cancel</button><button class="btn-save" id="saveBtn" onclick="saveEdit()">Save</button></div>
  </div>
</div>

<!-- Settings Modal -->
<div class="modal-bg" id="settingsModal">
  <div class="modal">
    <div class="modal-hd"><h2>Settings</h2><button class="close" onclick="closeSettings()">&times;</button></div>
    <div class="modal-body">
      <div class="field"><label>Model</label><select id="cfgModel"><option value="large-v3">large-v3 (best)</option><option value="medium">medium (faster)</option><option value="small">small (fastest)</option></select></div>
      <div class="field"><label>Device</label><select id="cfgDevice"><option value="cuda">GPU (CUDA)</option><option value="cpu">CPU</option></select></div>
      <div class="field"><label>Language (blank = auto-detect)</label><input id="cfgLang" placeholder="en, ar, fr, etc."></div>
      <div class="field"><label>Beam Size</label><input id="cfgBeam" type="number" value="5" min="1" max="10"></div>
    </div>
    <div class="modal-ft"><button class="btn-cancel" onclick="closeSettings()">Cancel</button><button class="btn-save" onclick="saveSettings()">Save Settings</button></div>
  </div>
</div>

<script>
let openCards=new Set(), last=null, editFile=null;

async function startTranscription(){
  document.getElementById('startBtn').disabled=true;
  await fetch('/api/start',{method:'POST'});
}

function toggle(n){openCards.has(n)?openCards.delete(n):openCards.add(n);if(last)render(last);}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}

async function openEdit(folder,name){
  editFile={folder,name};
  document.getElementById('editTitle').textContent='Edit: '+name;
  const r=await fetch(`/api/transcript/${folder}/${name}`);
  document.getElementById('editArea').value=await r.text();
  document.getElementById('editModal').classList.add('show');
}
function closeEdit(){document.getElementById('editModal').classList.remove('show');editFile=null;}
async function saveEdit(){
  if(!editFile)return;
  await fetch(`/api/transcript/${editFile.folder}/${editFile.name}`,{method:'PUT',body:document.getElementById('editArea').value});
  closeEdit();
}

async function openSettings(){
  const r=await fetch('/api/config');const c=await r.json();
  document.getElementById('cfgModel').value=c.model||'large-v3';
  document.getElementById('cfgDevice').value=c.device||'cuda';
  document.getElementById('cfgLang').value=c.language||'';
  document.getElementById('cfgBeam').value=c.beam_size||5;
  document.getElementById('settingsModal').classList.add('show');
}
function closeSettings(){document.getElementById('settingsModal').classList.remove('show');}
async function saveSettings(){
  const cfg={model:document.getElementById('cfgModel').value,device:document.getElementById('cfgDevice').value,language:document.getElementById('cfgLang').value||null,beam_size:parseInt(document.getElementById('cfgBeam').value)||5,compute:document.getElementById('cfgDevice').value==='cuda'?'float16':'int8'};
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
  closeSettings();
}

function render(d){
  last=d;
  const vids=d.videos||{},total=d.total_videos||0;
  const done=Object.values(vids).filter(v=>v.status==='done').length;
  const segs=Object.values(vids).reduce((s,v)=>s+(v.segments||[]).length,0);
  const dev=(d.device||'?').toUpperCase();
  const st=d.status||'idle';

  // Start button
  const sb=document.getElementById('startBtn');
  sb.disabled=(st==='loading'||st==='transcribing');
  sb.innerHTML=st==='transcribing'?'&#9654; Running...':st==='loading'?'Loading...':st==='done'?'&#9654; Run Again':'&#9654; Start Transcription';

  // Subtitle
  const sub=document.getElementById('sub');
  if(st==='loading') sub.textContent=`Loading ${d.model} on ${dev}...`;
  else if(st==='transcribing') sub.textContent=`Transcribing ${d.current_video||''} [${d.current_idx}/${total}] on ${dev}`;
  else if(st==='done') sub.textContent=`Completed in ${d.total_time||'?'}`;
  else if(st==='error') sub.textContent=`Error: ${d.error||'Unknown'}`;
  else sub.textContent='Ready — click Start to begin';

  // Pills
  const dc=st==='done'?'grn':st==='transcribing'?'orn':st==='loading'?'blu':'gry';
  document.getElementById('pills').innerHTML=`
    <div class="pill"><span class="dot ${dc}"></span>${st}</div>
    <div class="pill"><span class="dot ${dev==='CUDA'?'blu':'gry'}"></span>${dev}</div>
    <div class="pill">${done}/${total} done</div>
    <div class="pill">${segs} segments</div>`;

  // Left col — input
  const inp=d.input_files||[];
  let lh=`<div class="pnl"><div class="pnl-hd">Input Videos<span class="cnt">${inp.length}</span></div>`;
  inp.forEach(f=>{lh+=`<div class="fr"><div class="l"><div class="ico ico-mp4">MP4</div><span class="fn">${esc(f.name)}</span></div><span class="fm">${f.size_mb} MB</span></div>`;});
  if(!inp.length) lh+=`<div class="empty">Drop .mp4 files in input/</div>`;
  lh+=`</div>`;
  document.getElementById('leftCol').innerHTML=lh;

  // Right col — outputs
  const txts=d.txt_files||[],srts=d.srt_files||[];
  let rh=`<div class="pnl"><div class="pnl-hd">Transcripts<span class="cnt">${txts.length}</span></div>`;
  txts.forEach(f=>{rh+=`<div class="fr"><div class="l"><div class="ico ico-txt">TXT</div><span class="fn">${esc(f.name)}</span></div><div><button class="dl-btn" onclick="openEdit('txt','${f.name}')">Edit</button><a class="dl-btn" href="/api/download/txt/${f.name}">DL</a></div></div>`;});
  if(!txts.length) rh+=`<div class="empty">No transcripts</div>`;
  rh+=`</div><div class="pnl" style="margin-top:.8rem"><div class="pnl-hd">Subtitles<span class="cnt">${srts.length}</span></div>`;
  srts.forEach(f=>{rh+=`<div class="fr"><div class="l"><div class="ico ico-srt">SRT</div><span class="fn">${esc(f.name)}</span></div><div><button class="dl-btn" onclick="openEdit('srt','${f.name}')">Edit</button><a class="dl-btn" href="/api/download/srt/${f.name}">DL</a></div></div>`;});
  if(!srts.length) rh+=`<div class="empty">No subtitles</div>`;
  rh+=`</div>`;
  document.getElementById('rightCol').innerHTML=rh;

  // Center — cards
  const list=d.video_list||[];
  let ch='';
  for(let idx=0;idx<list.length;idx++){
    const name=list[idx],v=vids[name]||{},vst=v.status||'waiting';
    const sg=v.segments||[],isO=openCards.has(name);
    const wk=v.output_name||`Transcript_Week_${idx+1}`;
    let meta=[];
    if(v.language)meta.push(v.language.toUpperCase());
    if(v.duration)meta.push(`${v.duration}s`);
    if(v.elapsed)meta.push(`${(v.elapsed/60).toFixed(1)} min`);
    if(v.speed)meta.push(v.speed);
    let pct=0;
    if(vst==='done')pct=100;
    else if(v.duration&&sg.length){const ls=sg[sg.length-1];if(ls?.end){const p=ls.end.split(/[:,]/);pct=Math.min(99,Math.round((+p[0]*3600+ +p[1]*60+ +p[2])/v.duration*100));}}
    const sym=vst==='done'?'&#10003;':vst==='transcribing'?'&#9654;':vst==='error'?'&#10007;':(idx+1);
    ch+=`<div class="vc ${vst==='transcribing'?'active':''} ${vst==='done'?'done':''} ${vst==='error'?'err':''}">
      <div class="vh" onclick="toggle('${name}')"><div class="l"><div class="num ${vst}">${sym}</div><div><div class="vn">${esc(name)}</div><div class="vm">${meta.join(' &middot; ')||'Queued'}</div><div class="vo">${wk}</div></div></div><span class="bdg ${vst}">${vst}</span></div>
      ${vst!=='waiting'?`<div class="vp"><div class="fill" style="width:${pct}%"></div></div>`:''}
      <div class="vb ${isO?'open':''}">
        ${sg.length?sg.map(s=>`<div class="seg"><span class="seg-ts">${s.start}</span><span class="seg-tx">${esc(s.text)}</span></div>`).join(''):`<div class="empty">${vst==='waiting'?'Queued':vst==='error'?(v.error||'Error'):'Processing...'}</div>`}
      </div>
      ${vst==='done'?`<div class="vactions"><button class="abtn" onclick="openEdit('txt','${wk}.txt')">Edit TXT</button><button class="abtn" onclick="openEdit('srt','${wk}.srt')">Edit SRT</button><a class="abtn" href="/api/download/txt/${wk}.txt">Download TXT</a><a class="abtn" href="/api/download/srt/${wk}.srt">Download SRT</a></div>`:''}
    </div>`;
  }
  document.getElementById('cards').innerHTML=ch||'<div class="empty">Place .mp4 files in input/ and click Start</div>';
}

async function poll(){try{const r=await fetch('/api/status');render(await r.json());}catch(e){}setTimeout(poll,2000);}
poll();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("\n  Transcripe Dashboard: http://localhost:5000")
    print("  Click 'Start Transcription' in the browser to begin.\n")
    app_flask.run(host="0.0.0.0", port=5000, debug=False)
