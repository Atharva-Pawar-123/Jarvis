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
