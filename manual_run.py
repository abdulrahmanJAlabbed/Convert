import time
import threading
import sys
from app import run_transcription, state

def monitor():
    last_status = None
    while True:
        status = state.get("status")
        if status in ("done", "error"):
            break
        current_vid = state.get("current_video")
        idx = state.get("current_idx")
        total = state.get("total_videos")
        
        vid_state = state.get("videos", {}).get(current_vid, {}) if current_vid else {}
        elapsed = vid_state.get("elapsed", 0)
        dur = vid_state.get("duration", "?")
        lang = vid_state.get("language", "?")
        
        msg = f"\rStatus: {status} | Video: {current_vid} [{idx}/{total}] | Lang: {lang} | Elapsed: {elapsed}s / Duration: {dur}s"
        if status != "idle" and status != "loading":
            sys.stdout.write(msg)
            sys.stdout.flush()
        
        time.sleep(2)
    print(f"\nFinal status: {state.get('status')} | Error: {state.get('error')}")

t = threading.Thread(target=monitor, daemon=True)
t.start()

start_time = time.time()
print("Starting transcription...")
run_transcription()
print(f"Done in {time.time() - start_time:.1f}s")
