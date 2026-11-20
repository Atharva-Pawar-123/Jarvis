"""
tests/v2/test_image_studio.py — Automated Test Suite for Image Studio Pro
========================================================================
Validates image uploads, visual database records, session creation,
lineage tracking, and asset persistence.
"""

import pytest
import os
import io
from pathlib import Path
from PIL import Image
from modules.image_studio_db import ImageStudioDB
from modules.image_edit import ImageEditEngine

@pytest.fixture
def temp_studio_db(tmp_path):
    db_file = tmp_path / "test_image_studio.db"
    return ImageStudioDB(db_path=str(db_file))

def test_visual_session_creation_and_listing(temp_studio_db):
    sess = temp_studio_db.create_session("vis_test_1", "Test Imagine Session", "generate")
    assert sess["session_id"] == "vis_test_1"
    assert sess["title"] == "Test Imagine Session"

    sessions = temp_studio_db.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "vis_test_1"

def test_add_and_query_visual_assets(temp_studio_db):
    sess = temp_studio_db.create_session("vis_test_2", "Portrait Studio")
    
    # 1. Add upload asset
    asset1 = temp_studio_db.add_asset(
        asset_type="uploaded",
        filepath="d:/fake/path1.png",
        session_id="vis_test_2",
        prompt="Original Photo"
    )
    assert asset1["id"] is not None
    assert asset1["asset_type"] == "uploaded"

    # 2. Add edited asset with parent lineage
    asset2 = temp_studio_db.add_asset(
        asset_type="edited",
        filepath="d:/fake/path2.png",
        session_id="vis_test_2",
        prompt="Turn into cyberpunk",
        parent_asset_id=asset1["id"]
    )
    assert asset2["parent_asset_id"] == asset1["id"]

    # 3. List assets in session
    session_data = temp_studio_db.get_session("vis_test_2")
    assert len(session_data["assets"]) == 2
    assert session_data["assets"][0]["id"] == asset1["id"]
    assert session_data["assets"][1]["id"] == asset2["id"]

def test_image_edit_engine_save_uploaded_image(tmp_path):
    engine = ImageEditEngine()
    engine.upload_dir = tmp_path / "uploads"
    engine.upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate synthetic image in memory
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    file_bytes = buf.getvalue()

    filepath, b64_str, w, h = engine.save_uploaded_image(file_bytes, "test_pic.png")
    assert os.path.exists(filepath)
    assert len(b64_str) > 0
    assert w == 200
    assert h == 200


def test_upload_security_and_format_validation(tmp_path):
    engine = ImageEditEngine()
    engine.upload_dir = tmp_path / "uploads"
    engine.upload_dir.mkdir(parents=True, exist_ok=True)

    # 1. Reject non-image fake payload
    fake_bytes = b"This is not a real image file."
    with pytest.raises(ValueError, match="Corrupted or invalid image payload"):
        engine.save_uploaded_image(fake_bytes, "fake.txt")

    # 2. Reject payload exceeding 25MB limit
    oversized = b"0" * (26 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        engine.save_uploaded_image(oversized, "big.png")


def test_foreign_key_and_cascade_behavior(temp_studio_db):
    # Verify foreign key enforcement: deleting parent asset should set parent_asset_id to NULL
    sess = temp_studio_db.create_session("vis_fk_test", "Lineage FK Test")
    
    asset1 = temp_studio_db.add_asset(
        asset_type="uploaded",
        filepath="d:/fake/fk1.png",
        session_id="vis_fk_test",
        prompt="Parent image"
    )
    asset2 = temp_studio_db.add_asset(
        asset_type="edited",
        filepath="d:/fake/fk2.png",
        session_id="vis_fk_test",
        prompt="Child image",
        parent_asset_id=asset1["id"]
    )
    assert asset2["parent_asset_id"] == asset1["id"]

    # Delete parent asset
    temp_studio_db.delete_asset(asset1["id"])
    
    # Reload session and verify child still exists with parent_asset_id set to None/NULL
    session_data = temp_studio_db.get_session("vis_fk_test")
    remaining_assets = session_data["assets"]
    assert len(remaining_assets) == 1
    assert remaining_assets[0]["id"] == asset2["id"]
    assert remaining_assets[0]["parent_asset_id"] is None


def test_session_workspace_state_persistence(temp_studio_db):
    sess = temp_studio_db.create_session("vis_ws_test", "Workspace State Test")
    assert sess["session_id"] == "vis_ws_test"

    # Save state
    workspace_data = {
        "editPrompt": "Add neon glow",
        "denoisingStrength": 0.55,
        "selectedEditModel": "local:Realistic_Vision_V5.1_Inpaint"
    }
    success = temp_studio_db.update_session_workspace_state("vis_ws_test", workspace_data)
    assert success is True

    # Retrieve and verify
    reloaded = temp_studio_db.get_session("vis_ws_test")
    assert reloaded is not None
    import json
    saved_state = json.loads(reloaded["workspace_state"])
    assert saved_state["editPrompt"] == "Add neon glow"
    assert saved_state["denoisingStrength"] == 0.55
    assert saved_state["selectedEditModel"] == "local:Realistic_Vision_V5.1_Inpaint"


def test_gpu_scheduler_media_queue():
    from modules.gpu_scheduler import GPUScheduler
    scheduler = GPUScheduler()

    # Enqueue two media jobs
    job1_id = scheduler.register_media_job("inpainting", {"prompt": "Cyberpunk city"})
    job2_id = scheduler.register_media_job("upscale", {"scale": 2.0})

    assert job1_id.startswith("media_")
    assert job2_id.startswith("media_")

    snapshot = scheduler.get_queue_snapshot()
    assert snapshot["queued_count"] == 2
    assert snapshot["total_jobs"] == 2

    # Transition job 1 to running
    scheduler.update_job_status(job1_id, "running", progress=0.25)
    assert scheduler.active_job_id == job1_id
    assert scheduler.get_job_status(job1_id)["progress"] == 0.25

    # Complete job 1
    scheduler.update_job_status(job1_id, "completed", progress=1.0)
    assert scheduler.active_job_id is None
    assert scheduler.get_job_status(job1_id)["status"] == "completed"

    # Transition job 2
    scheduler.update_job_status(job2_id, "running", progress=0.5)
    assert scheduler.active_job_id == job2_id


def test_video_studio_motion_synthesis():
    from modules.video_studio import VideoStudioEngine
    import io
    import base64
    from PIL import Image

    engine = VideoStudioEngine()
    # Create simple 64x64 test image
    test_img = Image.new("RGB", (64, 64), color=(0, 200, 255))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Generate a short 0.25s test video (4 frames at 16fps)
    video_bytes, vid_path = engine.generate_motion_video(
        image_b64=b64_str,
        motion_type="zoom_in",
        duration_seconds=0.25,
        fps=16
    )

    assert video_bytes is not None
    assert len(video_bytes) > 0
    assert vid_path is not None
    import os
    assert os.path.exists(vid_path)


