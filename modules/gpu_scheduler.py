"""
modules/gpu_scheduler.py — Hardware-Aware VRAM & Model Resource Manager
========================================================================
Designed specifically for consumer GPUs (NVIDIA RTX 3050 6GB Laptop VRAM, 16GB RAM).
Enforces mutually exclusive execution rules to prevent CUDA Out-of-Memory crashes:
- LLM reasoning (qwen2.5:7b)
- Local Image Generation (Stable Diffusion Forge on port 7860)
- Vision models (llava:7b / moondream)

Models are dynamically parked or evicted from VRAM via Ollama's `keep_alive: 0` API.
"""

import logging
import asyncio
import requests
from typing import Optional

import config

logger = logging.getLogger(__name__)


class GPUScheduler:
    """Manages VRAM budgets to prevent collisions on a 6GB VRAM GPU."""

    def __init__(self):
        self.ollama_base = getattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._lock = asyncio.Lock()
        self.active_vram_consumer: str = "llm"  # 'llm' | 'forge' | 'vision'
        self.media_queue = asyncio.Queue()
        self.active_job_id: Optional[str] = None
        self.jobs: dict = {}  # job_id -> {status, progress, error, result}

    async def prepare_for_image_gen(self):
        """Unload or park LLM models from GPU VRAM before firing Forge SD."""
        async with self._lock:
            if self.active_vram_consumer == "forge":
                return

            logger.info("GPU Scheduler: Freeing VRAM for Local Image Generation (Forge)...")
            try:
                # Eject active models from Ollama VRAM by sending keep_alive: 0
                for model in [config.PRIMARY_MODEL, config.FAST_MODEL]:
                    await asyncio.to_thread(self._unload_ollama_model, model)
            except Exception as e:
                logger.warning(f"Could not cleanly unload Ollama model: {e}")

            self.active_vram_consumer = "forge"

    async def prepare_for_llm(self):
        """Prepares GPU for language model reasoning."""
        async with self._lock:
            if self.active_vram_consumer == "llm":
                return

            logger.info("GPU Scheduler: Restoring VRAM for Primary LLM...")
            self.active_vram_consumer = "llm"

    def _unload_ollama_model(self, model_name: str):
        """Calls Ollama generate with keep_alive=0 to immediately eject weights from VRAM."""
        try:
            url = f"{self.ollama_base}/api/generate"
            payload = {"model": model_name, "keep_alive": 0}
            requests.post(url, json=payload, timeout=3)
        except Exception:
            pass

    def get_gpu_telemetry(self) -> dict:
        """Reads GPU memory usage via nvidia-smi."""
        import subprocess
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                used = float(parts[0])
                total = float(parts[1])
                temp = float(parts[2]) if len(parts) > 2 else 0.0
                return {
                    "vram_used_mb": int(used),
                    "vram_total_mb": int(total),
                    "vram_percent": round((used / total) * 100, 1),
                    "gpu_temp_c": int(temp),
                    "active_consumer": self.active_vram_consumer
                }
        except Exception:
            pass

        return {
            "vram_used_mb": 0,
            "vram_total_mb": 6144,
            "vram_percent": 0.0,
            "gpu_temp_c": 0,
            "active_consumer": self.active_vram_consumer
        }

    def register_media_job(self, job_type: str, metadata: dict) -> str:
        """Enqueues a new media task into the FIFO queue and returns its unique tracking ID."""
        import uuid
        job_id = f"media_{uuid.uuid4().hex[:8]}"
        self.jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "queued",
            "progress": 0.0,
            "metadata": metadata,
            "error": None
        }
        return job_id

    def update_job_status(self, job_id: str, status: str, progress: float = 0.0, error: Optional[str] = None):
        """Updates status and progress of a tracked media job."""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["progress"] = progress
            if error:
                self.jobs[job_id]["error"] = error
            if status == "running":
                self.active_job_id = job_id
            elif status in ("completed", "failed"):
                if self.active_job_id == job_id:
                    self.active_job_id = None

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Returns the current state and metadata of a specific media job."""
        return self.jobs.get(job_id)

    def get_queue_snapshot(self) -> dict:
        """Returns a snapshot of the active job, queued count, and recent job history."""
        active = self.jobs.get(self.active_job_id) if self.active_job_id else None
        queued = [j for j in self.jobs.values() if j.get("status") == "queued"]
        completed = [j for j in self.jobs.values() if j.get("status") in ("completed", "failed")]
        return {
            "active_job": active,
            "queued_count": len(queued),
            "completed_count": len(completed),
            "recent_jobs": list(self.jobs.values())[-10:],
            "active_vram_consumer": self.active_vram_consumer
        }

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Returns the current execution state of a media job."""
        return self.jobs.get(job_id)

    def get_queue_snapshot(self) -> dict:
        """Returns full queue health, pending count, and active job details."""
        pending = [j for j in self.jobs.values() if j["status"] == "queued"]
        return {
            "active_job_id": self.active_job_id,
            "queued_count": len(pending),
            "total_jobs": len(self.jobs),
            "jobs": list(self.jobs.values())[-10:] # last 10 jobs
        }
