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
