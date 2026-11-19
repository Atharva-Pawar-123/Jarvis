"""
scripts/download_single_model.py
Dedicated script to download Realistic_Vision_V5.1_fp16-no-ema-inpainting.safetensors
when the user is ready.
"""

import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path("d:/JARVIS")
SD_MODELS_DIR = BASE_DIR / "tools" / "forge" / "webui" / "models" / "Stable-diffusion"
SD_MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_INFO = {
    "name": "Realistic_Vision_V5.1_fp16-no-ema-inpainting.safetensors",
    "url": "https://civitai.com/api/download/models/130090?fileId=94320",
    "dest": SD_MODELS_DIR / "Realistic_Vision_V5.1_fp16-no-ema-inpainting.safetensors",
    "size_expected_mb": 2033
}

def download():
    name = MODEL_INFO["name"]
    url = MODEL_INFO["url"]
    dest = MODEL_INFO["dest"]
    expected_mb = MODEL_INFO["size_expected_mb"]

    if dest.exists() and dest.stat().st_size > 1000 * 1024 * 1024:
        print(f"[SKIP] {name} already exists ({dest.stat().st_size / (1024*1024):.1f} MB).")
        return True

    print(f"\n[DOWNLOADING] {name} (~{expected_mb} MB)...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8 * 1024 * 1024  # 8MB chunks
            last_report = 0
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                
                now = time.time()
                if now - last_report >= 3:
                    pct = (downloaded / total_size * 100) if total_size else 0
                    mb = downloaded / (1024 * 1024)
                    speed = mb / max(0.1, now - start_time)
                    print(f"  {name}: {mb:.1f} MB ({pct:.1f}%) @ {speed:.2f} MB/s", flush=True)
                    last_report = now
                    
        elapsed = time.time() - start_time
        final_mb = dest.stat().st_size / (1024 * 1024)
        print(f"[COMPLETED] {name} in {elapsed:.1f}s ({final_mb:.1f} MB).")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download {name}: {e}")
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False

if __name__ == "__main__":
    ok = download()
    sys.exit(0 if ok else 1)
