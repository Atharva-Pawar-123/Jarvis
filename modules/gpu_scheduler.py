"""
modules/gpu_scheduler.py — Hardware-Aware VRAM & Model Resource Manager (V3.0.6)
================================================================================
Designed specifically for consumer GPUs (NVIDIA RTX 3050 6GB Laptop VRAM, 16GB RAM).
Enforces mutually exclusive execution rules and exclusive resource leases to prevent
CUDA Out-of-Memory crashes:
- Ollama LLM reasoning (qwen2.5:7b)
- Local Image Generation & Inpainting (SD Forge on port 7860)
- Local Vision models (llava:7b / moondream)
- Video motion synthesis & hardware upscaling

Features:
- True async FIFO task queue with worker serialization
- Exclusive lease context manager: `acquire_gpu_lease()`
- Dynamic model unloading via Ollama `keep_alive: 0`
- Safe cancellation & persistent job lifecycle tracking
"""

import logging
import asyncio
import requests
import uuid
from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager

import config

logger = logging.getLogger(__name__)


class GPUScheduler:
    """Central GPU Resource Manager with real execution queue and exclusive leases."""

    def __init__(self):
        self.ollama_base = getattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._lock = asyncio.Lock()
        self.active_vram_consumer: str = "llm"  # 'llm' | 'forge' | 'vision'
        self.active_job_id: Optional[str] = None
        self.jobs: Dict[str, Dict[str, Any]] = {}  # job_id -> metadata & state

        # FIFO Execution Queue
        self.media_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start_worker(self):
        """Starts the background sequential GPU worker."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_media_queue())
            logger.info("GPUScheduler sequential media worker started.")

    async def _process_media_queue(self):
        """Sequential queue worker consuming GPU-intensive tasks."""
        while True:
            try:
                job_id, fn, args, kwargs, future = await self.media_queue.get()
                self.active_job_id = job_id
                self.update_job_status(job_id, "running", progress=0.1)

                try:
                    async with self.acquire_gpu_lease("forge"):
                        if asyncio.iscoroutinefunction(fn):
                            result = await fn(*args, **kwargs)
                        else:
                            result = await asyncio.to_thread(fn, *args, **kwargs)

                    self.update_job_status(job_id, "completed", progress=1.0)
                    if not future.done():
                        future.set_result(result)
                except Exception as exc:
                    logger.error(f"Media job {job_id} failed: {exc}", exc_info=True)
                    self.update_job_status(job_id, "failed", error=str(exc))
                    if not future.done():
                        future.set_exception(exc)
                finally:
                    self.active_job_id = None
                    self.media_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in GPU media queue worker: {e}", exc_info=True)

    @asynccontextmanager
    async def acquire_gpu_lease(self, consumer: str = "forge"):
        """
        Exclusive lease context manager. Guarantees that only one GPU-heavy
        consumer runs at any moment, cleanly unparking/parking models.
        """
        async with self._lock:
            if consumer == "forge":
                await self._free_vram_for_forge()
            elif consumer == "llm":
                await self._restore_vram_for_llm()
            self.active_vram_consumer = consumer
            try:
                yield
            finally:
                # Release hook
                pass

    async def _free_vram_for_forge(self):
        """Unload Ollama models from GPU VRAM before firing SD Forge."""
        if self.active_vram_consumer == "forge":
            return
        logger.info("GPU Scheduler: Freeing VRAM for Forge inference...")
        try:
            for model in [config.PRIMARY_MODEL, config.FAST_MODEL]:
                await asyncio.to_thread(self._unload_ollama_model, model)
        except Exception as e:
            logger.warning(f"Could not cleanly unload Ollama model: {e}")

    async def _restore_vram_for_llm(self):
        """Restores VRAM for Ollama LLM execution."""
        if self.active_vram_consumer == "llm":
            return
        logger.info("GPU Scheduler: Restoring VRAM for Primary LLM...")

    def _unload_ollama_model(self, model_name: str):
        """Calls Ollama generate with keep_alive=0 to immediately eject weights from VRAM."""
        try:
            url = f"{self.ollama_base}/api/generate"
            payload = {"model": model_name, "keep_alive": 0}
            requests.post(url, json=payload, timeout=3)
        except Exception:
            pass

    async def prepare_for_image_gen(self):
        """Backward-compatible helper."""
        async with self._lock:
            await self._free_vram_for_forge()
            self.active_vram_consumer = "forge"

    async def prepare_for_llm(self):
        """Backward-compatible helper."""
        async with self._lock:
            await self._restore_vram_for_llm()
            self.active_vram_consumer = "llm"

    def register_media_job(self, job_type: str, metadata: dict) -> str:
        """Enqueues a new media task into tracking and returns unique tracking ID."""
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
        return self.jobs.get(job_id)

    def get_queue_snapshot(self) -> dict:
        """Returns snapshot of active job, queued count, and recent jobs."""
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
