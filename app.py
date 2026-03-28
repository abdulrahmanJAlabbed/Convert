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

# PPTX Slides paths
PPTX_IN   = ROOT / "slides" / "pptx"
PDF_OUT   = ROOT / "slides" / "pdf"
IMG_OUT   = ROOT / "slides" / "images"

for d in (INPUT_DIR, OUT_DIR, TXT_DIR, SRT_DIR, CACHE_DIR, PPTX_IN, PDF_OUT, IMG_OUT):
    d.mkdir(parents=True, exist_ok=True)
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
    # PPTX related
    "slides_status": "idle", # idle | converting
    "slides": {},           # name -> {status, format, progress}
}
state_lock = threading.Lock()
transcription_thread = None
slides_thread = None


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

        # Check for existing results to resume/skip
        if txt_path.exists() and srt_path.exists() and txt_path.stat().st_size > 0:
            print(f"  [Resume] Found existing transcript for {name}, skipping...")
            try:
                with state_lock:
                    state["videos"][name]["status"] = "done"
                    state["videos"][name]["elapsed"] = 0
                    state["videos"][name]["speed"] = "resumed"
                    state["videos"][name]["txt"] = f"output/txt/{week}.txt"
                    state["videos"][name]["srt"] = f"output/srt/{week}.srt"
                    state["completed"] = idx
                continue
            except Exception as e:
                print(f"  [Resume] Error marking {name} as done: {e}")

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


from convert_pptx import PPTXConverter
def run_slides_conversion(files, fmt):
    global state
    converter = PPTXConverter()
    
    with state_lock:
        state["slides_status"] = "converting"
        for f in files:
            state["slides"][f] = {"status": "converting", "format": fmt}

    for f in files:
        pptx_path = PPTX_IN / f
        try:
            if fmt == "pdf":
                out_path = PDF_OUT / (Path(f).stem + ".pdf")
                success = converter.convert_to_pdf(pptx_path, out_path)
            else:
                out_dir = IMG_OUT / Path(f).stem
                success = converter.convert_to_images(pptx_path, out_dir, fmt)
            
            with state_lock:
                state["slides"][f]["status"] = "done" if success else "error"
        except Exception as e:
            with state_lock:
                state["slides"][f]["status"] = "error"
                state["slides"][f]["error"] = str(e)

    with state_lock:
        still_running = any(v["status"] == "converting" for v in state["slides"].values())
        if not still_running:
            state["slides_status"] = "idle"


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
    d = TXT_DIR if folder == "txt" else SRT_DIR if folder == "srt" else \
        PDF_OUT if folder == "pdf" else None
    
    # Special case for images (zip them or return individual)
    if folder == "images":
        img_dir = IMG_OUT / name
        if img_dir.is_dir():
            # For simplicity, if it's a folder, we zip it on the fly or just return it if it's already a file
            # Let's say we zip it
            shutil.make_archive(str(img_dir), 'zip', str(img_dir))
            return send_file(str(img_dir) + ".zip", as_attachment=True)

    if d:
        p = d / name
        if p.exists():
            return send_file(str(p), as_attachment=True)
    return Response("Not found", status=404)


@app_flask.route("/api/slides/status")
def api_slides_status():
    with state_lock:
        data = {
            "status": state["slides_status"],
            "files": [
                {
                    "name": f.name, 
                    "size_mb": round(f.stat().st_size / 1e6, 2),
                    "state": state["slides"].get(f.name, {"status": "idle"})
                }
                for f in sorted(PPTX_IN.glob("*.pptx"))
            ],
            "outputs": {
                "pdf": [f.name for f in sorted(PDF_OUT.glob("*.pdf"))],
                "images": [f.name for f in sorted(IMG_OUT.iterdir()) if f.is_dir()]
            }
        }
    return Response(json.dumps(data), content_type="application/json")


@app_flask.route("/api/slides/convert", methods=["POST"])
def api_slides_convert():
    global slides_thread
    req = request.get_json()
    files = req.get("files", [])
    fmt = req.get("format", "pdf")
    
    if not files:
        files = [f.name for f in PPTX_IN.glob("*.pptx")]
    
    slides_thread = threading.Thread(target=run_slides_conversion, args=(files, fmt), daemon=True)
    slides_thread.start()
    return Response('{"ok":true}', content_type="application/json")


@app_flask.route("/api/slides/upload", methods=["POST"])
def api_slides_upload():
    if 'file' not in request.files:
        return Response('{"error":"No file"}', status=400)
    file = request.files['file']
    if file.filename == '':
        return Response('{"error":"Empty filename"}', status=400)
    if not file.filename.endswith('.pptx'):
        return Response('{"error":"Only .pptx allowed"}', status=400)
    
    file.save(PPTX_IN / file.filename)
    return Response('{"ok":true}', content_type="application/json")


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

/* Navigation */
.nav{display:flex;gap:1rem;margin-bottom:1.5rem;border-bottom:1px solid var(--border);}
.nav-item{padding:.7rem 1rem;cursor:pointer;font-size:.85rem;font-weight:600;color:var(--t2);border-bottom:2px solid transparent;transition:all .2s;}
.nav-item.active{color:var(--ac2);border-color:var(--ac);}
.nav-item:hover{color:var(--t1);}

/* Toolbar */
.toolbar{display:flex;gap:.6rem;margin-bottom:1.5rem;flex-wrap:wrap;align-items:center;}
.btn{padding:.55rem 1.1rem;border-radius:var(--r2);font-size:.78rem;font-weight:600;border:none;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:.4rem;}
.btn-start{background:var(--grn);color:#000;} .btn-start:hover{background:#2bc489;transform:translateY(-1px);}
.btn-start:disabled{opacity:.4;cursor:not-allowed;transform:none;}
.btn-settings{background:var(--s2);color:var(--t2);border:1px solid var(--border);} .btn-settings:hover{border-color:var(--ac);color:var(--t1);}

/* Layout */
.layout{display:grid;grid-template-columns:260px 1fr 260px;gap:1.2rem;}
@media(max-width:1100px){.layout{grid-template-columns:1fr;}}
.tab-content{display:none;}
.tab-content.active{display:block;}

/* Panels */
.pnl{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;}
.pnl-hd{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--t2);padding:.8rem .9rem .45rem;display:flex;align-items:center;gap:.4rem;}
.pnl-hd .cnt{background:var(--s3);padding:.1rem .4rem;border-radius:100px;font-size:.58rem;color:var(--t3);}
.fr{display:flex;align-items:center;justify-content:space-between;padding:.5rem .9rem;border-top:1px solid var(--border);font-size:.75rem;transition:background .12s;cursor:default;}
.fr:hover{background:var(--s2);}
.l{display:flex;align-items:center;gap:.5rem;}
.ico{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:800;flex-shrink:0;}
.ico-mp4{background:var(--blu-d);color:var(--blu);} .ico-txt{background:var(--grn-d);color:var(--grn);} .ico-srt{background:var(--orn-d);color:var(--orn);}
.ico-pptx{background:var(--red-d);color:var(--red);} .ico-pdf{background:var(--pur-d);color:var(--ac2);}
.fn{font-weight:500;font-size:.75rem;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;} 
.fm{color:var(--t3);font-size:.65rem;}
.empty{padding:1.5rem;text-align:center;color:var(--t3);font-size:.78rem;font-style:italic;}
.dl-btn{background:none;border:none;color:var(--t3);cursor:pointer;font-size:.7rem;padding:4px 8px;border-radius:5px;transition:all .15s;text-decoration:none;}
.dl-btn:hover{background:var(--s3);color:var(--ac2);}

/* Conversion Table */
.slides-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;}
.scard{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);padding:1rem;display:flex;flex-direction:column;gap:.8rem;}
.scard-hd{display:flex;justify-content:space-between;align-items:flex-start;}
.scard-status{font-size:.6rem;font-weight:700;text-transform:uppercase;padding:.2rem .5rem;border-radius:100px;}
.status-idle{background:var(--s3);color:var(--t3);}
.status-converting{background:var(--pur-d);color:var(--ac2);animation:blink 1.5s infinite;}
.status-done{background:var(--grn-d);color:var(--grn);}
.status-error{background:var(--red-d);color:var(--red);}
.scard-ops{display:flex;gap:.5rem;margin-top:.5rem;}

.upload-zone{border:2px dashed var(--border);border-radius:var(--r);padding:2rem;text-align:center;color:var(--t2);cursor:pointer;transition:all .2s;margin-bottom:1.5rem;}
.upload-zone:hover{border-color:var(--ac);background:var(--s1);}

/* Modals & Inputs */
.modal-bg{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);z-index:100;justify-content:center;align-items:center;backdrop-filter:blur(5px);}
.modal-bg.show{display:flex;}
.modal{background:var(--s1);border:1px solid var(--border);border-radius:var(--r);width:90%;max-width:700px;max-height:85vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.5);}
.modal-hd{display:flex;justify-content:space-between;align-items:center;padding:1.2rem 1.5rem;border-bottom:1px solid var(--border);}
.modal-hd h2{font-size:1.1rem;font-weight:700;}
.close{background:none;border:none;color:var(--t3);cursor:pointer;font-size:1.5rem;line-height:1;} .close:hover{color:#fff;}
.modal-body{padding:1.5rem;overflow-y:auto;flex:1;}
textarea{width:100%;min-height:350px;background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);color:var(--t1);font-family:'Courier New',monospace;font-size:.85rem;padding:1rem;resize:vertical;line-height:1.6;outline:none;}
textarea:focus{border-color:var(--ac);}
.field{margin-bottom:1.2rem;}
.field label{display:block;font-size:.68rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem;}
select,input{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);color:var(--t1);padding:.6rem .8rem;font-size:.85rem;outline:none;}
select:focus,input:focus{border-color:var(--ac);}
.btn-save{background:var(--ac);color:#fff;padding:.6rem 1.2rem;border:none;border-radius:var(--r2);font-size:.82rem;font-weight:700;cursor:pointer;}
.btn-cancel{background:var(--s3);color:var(--t2);padding:.6rem 1.2rem;border:1px solid var(--border);border-radius:var(--r2);font-size:.82rem;cursor:pointer;}

::-webkit-scrollbar{width:6px;}::-webkit-scrollbar-track{background:transparent;}::-webkit-scrollbar-thumb{background:var(--border);border-radius:10px;}
</style>
</head>
<body>
<div class="shell">
  <div class="hdr">
    <div><h1>Transcripe</h1><p class="sub" id="sub">Initializing...</p></div>
    <div class="pills" id="pills"></div>
  </div>
  
  <div class="nav">
    <div class="nav-item active" onclick="setTab('transcription')">Transcription</div>
    <div class="nav-item" onclick="setTab('presentations')">Presentations</div>
  </div>

  <!-- Transcription Tab -->
  <div id="tab-transcription" class="tab-content active">
    <div class="toolbar">
      <button class="btn btn-start" id="startBtn" onclick="startTranscription()">&#9654; Start Processing</button>
      <button class="btn btn-settings" onclick="openSettings()">&#9881; Settings</button>
    </div>
    <div class="layout">
      <div id="videoInputs"></div>
      <div class="cards" id="videoCards"></div>
      <div id="videoOutputs"></div>
    </div>
  </div>

  <!-- Presentations Tab -->
  <div id="tab-presentations" class="tab-content">
    <div class="upload-zone" onclick="document.getElementById('pptxUpload').click()">
      <p>Click to Upload PowerPoint (.pptx)</p>
      <input type="file" id="pptxUpload" style="display:none" accept=".pptx" onchange="uploadPPTX(this)">
    </div>
    
    <div class="layout" style="grid-template-columns: 280px 1fr;">
      <div id="pptxList"></div>
      <div class="slides-grid" id="slidesGrid"></div>
    </div>
  </div>
</div>

<!-- Edit Modal -->
<div class="modal-bg" id="editModal">
  <div class="modal">
    <div class="modal-hd"><h2 id="editTitle">Edit</h2><button class="close" onclick="closeEdit()">&times;</button></div>
    <div class="modal-body"><textarea id="editArea"></textarea></div>
    <div class="modal-ft" style="padding:1rem;border-top:1px solid var(--border);display:flex;justify-content:flex-end;gap:.5rem;">
      <button class="btn-cancel" onclick="closeEdit()">Cancel</button>
      <button class="btn-save" onclick="saveEdit()">Save Changes</button>
    </div>
  </div>
</div>

<!-- Settings Modal -->
<div class="modal-bg" id="settingsModal">
  <div class="modal" style="max-width:500px">
    <div class="modal-hd"><h2>Configuration</h2><button class="close" onclick="closeSettings()">&times;</button></div>
    <div class="modal-body">
      <div class="field"><label>Whisper Model</label><select id="cfgModel"><option value="large-v3">large-v3 (Best)</option><option value="medium">medium</option><option value="small">small</option></select></div>
      <div class="field"><label>Device</label><select id="cfgDevice"><option value="cuda">GPU (CUDA)</option><option value="cpu">CPU Only</option></select></div>
      <div class="field"><label>Language (ISO Code)</label><input id="cfgLang" placeholder="e.g. en, ar, fr"></div>
    </div>
    <div class="modal-ft" style="padding:1rem;border-top:1px solid var(--border);display:flex;justify-content:flex-end;gap:.5rem;">
      <button class="btn-cancel" onclick="closeSettings()">Cancel</button>
      <button class="btn-save" onclick="saveSettings()">Apply Settings</button>
    </div>
  </div>
</div>

<script>
let currentTab = 'transcription';
let openCards = new Set();
let editFile = null;

function setTab(t) {
  currentTab = t;
  document.querySelectorAll('.nav-item').forEach(i => i.classList.toggle('active', i.textContent.toLowerCase() === t));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-'+t));
}

async function startTranscription() {
  document.getElementById('startBtn').disabled = true;
  await fetch('/api/start', {method:'POST'});
}

async function convertPPTX(name, fmt) {
  await fetch('/api/slides/convert', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({files: [name], format: fmt})
  });
}

async function uploadPPTX(input) {
  if(!input.files.length) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  await fetch('/api/slides/upload', {method:'POST', body:fd});
  input.value = '';
}

function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function toggleCard(n){openCards.has(n)?openCards.delete(n):openCards.add(n);}

async function openEdit(folder,name){
  editFile={folder,name};
  document.getElementById('editTitle').textContent='Edit: '+name;
  const r=await fetch(`/api/transcript/${folder}/${name}`);
  document.getElementById('editArea').value=await r.text();
  document.getElementById('editModal').classList.add('show');
}
function closeEdit(){document.getElementById('editModal').classList.remove('show');}
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
  document.getElementById('settingsModal').classList.add('show');
}
function closeSettings(){document.getElementById('settingsModal').classList.remove('show');}
async function saveSettings(){
  const cfg={model:document.getElementById('cfgModel').value,device:document.getElementById('cfgDevice').value,language:document.getElementById('cfgLang').value||null,compute:document.getElementById('cfgDevice').value==='cuda'?'float16':'int8'};
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
  closeSettings();
}

async function poll() {
  try {
    const r1 = await fetch('/api/status');
    const d1 = await r1.json();
    renderTranscription(d1);
    
    if(currentTab === 'presentations') {
      const r2 = await fetch('/api/slides/status');
      const d2 = await r2.json();
      renderSlides(d2);
    }
  } catch(e) {}
  setTimeout(poll, 2000);
}

function renderTranscription(d) {
  const vids=d.videos||{}, total=d.total_videos||0;
  const done=Object.values(vids).filter(v=>v.status==='done').length;
  const dev=(d.device||'?').toUpperCase();
  const st=d.status||'idle';

  document.getElementById('startBtn').disabled = (st==='loading'||st==='transcribing');
  document.getElementById('startBtn').textContent = st==='transcribing'?'Processing...':st==='loading'?'Loading Model...':'Start Processing';
  
  const sub = document.getElementById('sub');
  if(st==='loading') sub.textContent = `Loading ${d.model} on ${dev}...`;
  else if(st==='transcribing') sub.textContent = `Processing ${d.current_video} [${d.current_idx}/${total}]`;
  else if(st==='done') sub.textContent = `Done! Total time: ${d.total_time}`;
  else sub.textContent = 'Ready to transcribe';

  const dc=st==='done'?'grn':st==='transcribing'?'orn':st==='loading'?'blu':'gry';
  document.getElementById('pills').innerHTML=`
    <div class="pill"><span class="dot ${dc}"></span>${st.toUpperCase()}</div>
    <div class="pill"><span class="dot ${dev==='CUDA'?'blu':'gry'}"></span>${dev}</div>
    <div class="pill">${done}/${total} COMPLETED</div>`;

  // Left col
  let lh=`<div class="pnl"><div class="pnl-hd">Source Videos<span class="cnt">${(d.input_files||[]).length}</span></div>`;
  (d.input_files||[]).forEach(f=>{lh+=`<div class="fr"><div class="l"><div class="ico ico-mp4">MP4</div><span class="fn">${esc(f.name)}</span></div><span class="fm">${f.size_mb}MB</span></div>`});
  document.getElementById('videoInputs').innerHTML = lh + '</div>';

  // Center cards
  let ch='';
  (d.video_list||[]).forEach((name, i)=>{
    const v=vids[name]||{}, vst=v.status||'waiting', isO=openCards.has(name);
    const meta = [v.language, v.duration?v.duration+'s':null, v.speed].filter(x=>x).join(' • ');
    ch+=`<div class="pnl" style="margin-bottom:.8rem;border-color:${vst==='transcribing'?'var(--ac)':''}">
      <div class="fr" style="padding:1rem;cursor:pointer" onclick="toggleCard('${name}');renderTranscription(lastData)">
        <div class="l"><div class="ico ico-mp4" style="background:${vst==='done'?'var(--grn-d)':'var(--s3)'}">${vst==='done'?'✓':i+1}</div>
        <div><div class="fn" style="max-width:none;font-size:.85rem">${esc(name)}</div><div class="fm">${meta||'Queued'}</div></div></div>
        <span class="scard-status status-${vst}">${vst}</span>
      </div>
      ${isO?`<div style="padding:0 1rem 1rem;font-size:.75rem;max-height:200px;overflow-y:auto;border-top:1px solid var(--border);padding-top:1rem">${(v.segments||[]).map(s=>`<div><span style="color:var(--ac2)">${s.start}</span> ${esc(s.text)}</div>`).join('') || '<div class="empty">Waiting for segments...</div>'}</div>`:''}
      ${vst==='done'?`<div class="fr" style="background:var(--s2);gap:.5rem"><button class="dl-btn" onclick="openEdit('txt','${v.output_name}.txt')">Edit TXT</button><a class="dl-btn" href="/api/download/txt/${v.output_name}.txt">Download</a></div>`:''}
    </div>`;
  });
  document.getElementById('videoCards').innerHTML = ch || '<div class="empty">Add MP4s to /input and click start</div>';
  window.lastData = d;

  // Right col
  let rh=`<div class="pnl"><div class="pnl-hd">Transcripts<span class="cnt">${(d.txt_files||[]).length}</span></div>`;
  (d.txt_files||[]).forEach(f=>{rh+=`<div class="fr"><div class="l"><div class="ico ico-txt">TXT</div><span class="fn">${esc(f.name)}</span></div><a class="dl-btn" href="/api/download/txt/${f.name}">DL</a></div>`});
  document.getElementById('videoOutputs').innerHTML = rh + '</div>';
}

function renderSlides(d) {
  let lh=`<div class="pnl"><div class="pnl-hd">Presentations<span class="cnt">${d.files.length}</span></div>`;
  d.files.forEach(f=>{
    lh+=`<div class="fr"><div class="l"><div class="ico ico-pptx">PPT</div><span class="fn">${esc(f.name)}</span></div><span class="fm">${f.size_mb}MB</span></div>`;
  });
  document.getElementById('pptxList').innerHTML = lh + '</div>';

  let gh='';
  d.files.forEach(f=>{
    const s = f.state;
    gh+=`<div class="scard">
      <div class="scard-hd">
        <div><div style="font-weight:700;font-size:.9rem">${esc(f.name)}</div><div class="fm">Format: ${s.format||'N/A'}</div></div>
        <span class="scard-status status-${s.status}">${s.status}</span>
      </div>
      <div class="scard-ops">
        <button class="btn btn-settings" style="flex:1;padding:.4rem" onclick="convertPPTX('${f.name}','pdf')">Convert to PDF</button>
        <button class="btn btn-settings" style="flex:1;padding:.4rem" onclick="convertPPTX('${f.name}','png')">To Images</button>
      </div>
      ${s.status==='done'?`<div style="display:flex;gap:.5rem;margin-top:.5rem">
        ${s.format==='pdf'?`<a class="dl-btn" style="flex:1;text-align:center" href="/api/download/pdf/${f.name.replace('.pptx','.pdf')}">Download PDF</a>`:''}
        ${s.format==='png' || s.format==='jpg'?`<a class="dl-btn" style="flex:1;text-align:center" href="/api/download/images/${f.name.replace('.pptx','')}">Download Images</a>`:''}
      </div>`:''}
    </div>`;
  });
  document.getElementById('slidesGrid').innerHTML = gh || '<div class="empty">Upload a .pptx file above to start</div>';
}

poll();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("\n  Transcripe Dashboard: http://localhost:5000")
    print("  Click 'Start Transcription' in the browser to begin.\n")
    app_flask.run(host="0.0.0.0", port=5000, debug=False)
