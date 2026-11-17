"""
tests/v2/test_gpu_scheduler.py — GPU Scheduler & VRAM Telemetry Tests
=====================================================================
Validates GPUScheduler:
  - Active VRAM consumer state transitions (llm <-> forge)
  - Ollama model eviction call logic (keep_alive: 0)
  - Telemetry gathering via nvidia-smi fallback handling
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.gpu_scheduler import GPUScheduler


@pytest.fixture
def gpu_scheduler():
    return GPUScheduler()


class TestGPUSchedulerTransitions:
    @pytest.mark.asyncio
    async def test_initial_state(self, gpu_scheduler):
        assert gpu_scheduler.active_vram_consumer == "llm"

    @pytest.mark.asyncio
    async def test_prepare_for_image_gen(self, gpu_scheduler):
        with patch.object(gpu_scheduler, "_unload_ollama_model") as mock_unload:
            await gpu_scheduler.prepare_for_image_gen()
            assert gpu_scheduler.active_vram_consumer == "forge"
            # Should have attempted to unload models
            assert mock_unload.call_count >= 1

    @pytest.mark.asyncio
    async def test_prepare_for_image_gen_idempotent(self, gpu_scheduler):
        gpu_scheduler.active_vram_consumer = "forge"
        with patch.object(gpu_scheduler, "_unload_ollama_model") as mock_unload:
            await gpu_scheduler.prepare_for_image_gen()
            # Already in forge state, should not re-trigger unloads
            assert mock_unload.call_count == 0

    @pytest.mark.asyncio
    async def test_prepare_for_llm(self, gpu_scheduler):
        gpu_scheduler.active_vram_consumer = "forge"
        await gpu_scheduler.prepare_for_llm()
        assert gpu_scheduler.active_vram_consumer == "llm"


class TestGPUTelemetry:
    def test_telemetry_nvidia_smi_success(self, gpu_scheduler):
        mock_output = "2048, 6144, 55\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            telemetry = gpu_scheduler.get_gpu_telemetry()
            assert telemetry["vram_used_mb"] == 2048
            assert telemetry["vram_total_mb"] == 6144
            assert telemetry["vram_percent"] == 33.3
            assert telemetry["gpu_temp_c"] == 55
            assert telemetry["active_consumer"] == gpu_scheduler.active_vram_consumer

    def test_telemetry_fallback_on_error(self, gpu_scheduler):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            telemetry = gpu_scheduler.get_gpu_telemetry()
            assert telemetry["vram_used_mb"] == 0
            assert telemetry["vram_total_mb"] == 6144
            assert telemetry["vram_percent"] == 0.0
            assert telemetry["gpu_temp_c"] == 0
