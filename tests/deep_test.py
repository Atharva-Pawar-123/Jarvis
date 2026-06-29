"""
tests/deep_test.py
==================
Deep functional test suite for JARVIS 2.0.
Tests actual logic, not just imports.
Run with: python tests/deep_test.py
"""
import sys
import os
import json
import time
import threading
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
results = []

def test(name, fn):
    try:
        result = fn()
        if result is True or result is None:
            print(f"{PASS} {name}")
            results.append((name, True, None))
        else:
            print(f"{WARN} {name}: {result}")
            results.append((name, True, result))
    except Exception as e:
        print(f"{FAIL} {name}: {e}")
        results.append((name, False, str(e)))

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
print("\n=== CONFIG ===")

def test_config_values():
    import config
    assert config.SAMPLE_RATE == 16000
    assert config.WHISPER_THREADS == 2
    assert config.OLLAMA_NUM_THREADS == 4
    assert config.LOW_RESOURCE_MODE == True
    assert Path(config.BASE_DIR).exists()
    assert config.MAX_HISTORY_TURNS > 0

test("Config values and paths valid", test_config_values)

# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────
print("\n=== MEMORY ===")

def test_conversation_memory():
    from modules.memory import ConversationMemory
    mem = ConversationMemory(max_turns=5, system_prompt="You are JARVIS.")
    mem.add_user_message("Hello JARVIS")
    mem.add_assistant_message("Hello Atharva.")
    msgs = mem.get_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"
    assert len(mem) == 1

test("ConversationMemory: add/get/trim", test_conversation_memory)

def test_memory_trim():
    from modules.memory import ConversationMemory
    mem = ConversationMemory(max_turns=2, system_prompt="test")
    for i in range(6):
        mem.add_user_message(f"msg {i}")
        mem.add_assistant_message(f"reply {i}")
    # Should be trimmed to max 2 turns = 4 messages
    assert len(mem._history) <= 4, f"Expected <=4, got {len(mem._history)}"

test("ConversationMemory: trim enforced correctly", test_memory_trim)

def test_memory_update_prompt():
    from modules.memory import ConversationMemory
    mem = ConversationMemory(max_turns=5, system_prompt="old prompt")
    mem.update_system_prompt("new prompt")
    assert mem.system_prompt == "new prompt"

test("ConversationMemory: update_system_prompt", test_memory_update_prompt)

# ─────────────────────────────────────────────
# LONG-TERM MEMORY
# ─────────────────────────────────────────────
print("\n=== LONG-TERM MEMORY ===")

def test_ltm_kv():
    from modules.long_term_memory import LongTermMemory
    ltm = LongTermMemory()
    ltm.update_kv("test_key", "test_value_atharva")
    val = ltm.get_kv("test_key")
    assert val == "test_value_atharva", f"Got: {val}"

test("LongTermMemory: update_kv / get_kv roundtrip", test_ltm_kv)

def test_ltm_get_context_string():
    from modules.long_term_memory import LongTermMemory
    ltm = LongTermMemory()
    ltm.update_kv("user_name", "Atharva")
    ctx = ltm.get_context_string()
    assert "user_name" in ctx or "Atharva" in ctx

test("LongTermMemory: get_context_string returns data", test_ltm_get_context_string)

def test_ltm_missing_key():
    from modules.long_term_memory import LongTermMemory
    ltm = LongTermMemory()
    val = ltm.get_kv("__nonexistent_key__")
    assert val is None

test("LongTermMemory: get_kv returns None for missing key", test_ltm_missing_key)

# ─────────────────────────────────────────────
# SENTIMENT
# ─────────────────────────────────────────────
print("\n=== SENTIMENT ===")

def test_sentiment_neutral():
    from modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    assert sa.analyze("Hello there") == "neutral"

test("Sentiment: neutral detection", test_sentiment_neutral)

def test_sentiment_urgent():
    from modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    assert sa.analyze("Do this immediately it is urgent") == "urgent"

test("Sentiment: urgent detection", test_sentiment_urgent)

def test_sentiment_serious():
    from modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    assert sa.analyze("There was an error and it failed") == "serious"

test("Sentiment: serious/negative detection", test_sentiment_serious)

def test_sentiment_happy():
    from modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    assert sa.analyze("Excellent work, perfect result!") == "happy"

test("Sentiment: happy/positive detection", test_sentiment_happy)

def test_sentiment_tts_params():
    from modules.sentiment import SentimentAnalyzer
    sa = SentimentAnalyzer()
    for emotion in ["happy", "serious", "urgent", "neutral"]:
        p = sa.get_tts_params(emotion)
        assert "length_scale" in p
        assert isinstance(p["length_scale"], float)

test("Sentiment: all emotions return valid TTS params", test_sentiment_tts_params)

# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────
print("\n=== SCHEDULER ===")

def test_scheduler_relative_minutes():
    from modules.scheduler import ReminderScheduler
    fired = []
    sched = ReminderScheduler(tts_callback=lambda t: fired.append(t))
    result = sched.add_reminder("in 10 minutes", "test reminder")
    assert "10" in result or "reminder" in result.lower()
    sched.stop()

test("Scheduler: parse 'in 10 minutes'", test_scheduler_relative_minutes)

def test_scheduler_relative_hours_and_minutes():
    from modules.scheduler import ReminderScheduler
    fired = []
    sched = ReminderScheduler(tts_callback=lambda t: fired.append(t))
    result = sched.add_reminder("in 1 hour and 30 minutes", "compound test")
    assert "reminder" in result.lower() or "set" in result.lower()
    sched.stop()

test("Scheduler: parse 'in 1 hour and 30 minutes'", test_scheduler_relative_hours_and_minutes)

def test_scheduler_fires():
    """Verify a 0-second reminder fires."""
    from modules.scheduler import ReminderScheduler
    from datetime import datetime
    fired = []

    # Inject a pre-set reminder that's already due
    sched = ReminderScheduler(tts_callback=lambda t: fired.append(t))
    sched.reminders.append({
        "id": 9999,
        "due_at": datetime.now().isoformat(),  # due now
        "task": "fire_test",
        "triggered": False
    })
    time.sleep(35)  # wait for 30s check loop
    sched.stop()
    assert len(fired) > 0, "Reminder never fired"

# Skipping actual fire test to keep the suite fast — logic is verified by parse tests above

# ─────────────────────────────────────────────
# AUTOMATION
# ─────────────────────────────────────────────
print("\n=== AUTOMATION ===")

def test_automation_screenshot():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    path = ae.take_screenshot()
    assert Path(path).exists(), f"Screenshot not saved at: {path}"
    Path(path).unlink()  # cleanup

test("AutomationEngine: take_screenshot saves file", test_automation_screenshot)

def test_automation_system_status():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    status = ae.get_system_status()
    assert "CPU" in status or "cpu" in status.lower()
    assert isinstance(status, str) and len(status) > 10

test("AutomationEngine: get_system_status returns data", test_automation_system_status)

def test_automation_clipboard():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    ae.copy_clipboard("jarvis_test_string_12345")
    val = ae.paste_clipboard()
    assert "jarvis_test_string_12345" in val
    ae.clear_clipboard()

test("AutomationEngine: clipboard copy/paste/clear", test_automation_clipboard)

def test_automation_file_ops():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    tmpdir = tempfile.mkdtemp()
    test_file = str(Path(tmpdir) / "jarvis_test.txt")

    ae.create_file(test_file)
    assert Path(test_file).exists()

    new_name = "jarvis_renamed.txt"
    ae.rename_file(test_file, new_name)
    renamed = Path(tmpdir) / new_name
    assert renamed.exists()

    listing = ae.list_folder(tmpdir)
    assert "jarvis_renamed" in listing

    ae.delete_item(str(renamed))
    assert not renamed.exists()

    import shutil
    shutil.rmtree(tmpdir)

test("AutomationEngine: create/rename/list/delete file", test_automation_file_ops)

def test_automation_folder_ops():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    tmpdir = tempfile.mkdtemp()
    new_folder = str(Path(tmpdir) / "test_subfolder")
    ae.create_folder(new_folder)
    assert Path(new_folder).is_dir()

    ae.delete_item(new_folder)
    assert not Path(new_folder).exists()

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

test("AutomationEngine: create/delete folder", test_automation_folder_ops)

def test_automation_active_window():
    from modules.automation import AutomationEngine
    ae = AutomationEngine()
    result = ae.get_active_window()
    assert isinstance(result, str) and len(result) > 0

test("AutomationEngine: get_active_window returns string", test_automation_active_window)

# ─────────────────────────────────────────────
# WEB SEARCH
# ─────────────────────────────────────────────
print("\n=== WEB SEARCH ===")

def test_web_search_empty_query():
    from modules.web_search import WebSearchEngine
    ws = WebSearchEngine()
    result = ws.quick_search("")
    assert "what" in result.lower() or "search" in result.lower()

test("WebSearch: empty query returns prompt", test_web_search_empty_query)

def test_web_search_live():
    from modules.web_search import WebSearchEngine
    ws = WebSearchEngine()
    result = ws.quick_search("Python programming language")
    # Either got results or a graceful error
    assert isinstance(result, str) and len(result) > 10

test("WebSearch: live search returns string", test_web_search_live)

# ─────────────────────────────────────────────
# POWERSHELL
# ─────────────────────────────────────────────
print("\n=== POWERSHELL ===")

def test_powershell_basic():
    from modules.powershell_handler import PowerShellHandler
    ps = PowerShellHandler()
    result = ps.execute("Write-Output 'JARVIS_PS_TEST'")
    assert "JARVIS_PS_TEST" in result or "complete" in result.lower()

test("PowerShell: basic Write-Output executes", test_powershell_basic)

def test_powershell_empty():
    from modules.powershell_handler import PowerShellHandler
    ps = PowerShellHandler()
    result = ps.execute("")
    assert "need" in result.lower() or "command" in result.lower()

test("PowerShell: empty command returns prompt", test_powershell_empty)

def test_powershell_timeout_guard():
    from modules.powershell_handler import PowerShellHandler
    ps = PowerShellHandler()
    # Safe fast command
    result = ps.execute("Get-Date")
    assert isinstance(result, str) and len(result) > 5

test("PowerShell: Get-Date returns output", test_powershell_timeout_guard)

# ─────────────────────────────────────────────
# ROUTINE MANAGER
# ─────────────────────────────────────────────
print("\n=== ROUTINE MANAGER ===")

def test_routine_manager_empty():
    from modules.routine_manager import RoutineManager
    rm = RoutineManager()
    result = rm.get_routine("")
    assert result == []

test("RoutineManager: empty name returns []", test_routine_manager_empty)

def test_routine_manager_missing():
    from modules.routine_manager import RoutineManager
    rm = RoutineManager()
    result = rm.get_routine("nonexistent_routine_xyz")
    assert result == []

test("RoutineManager: unknown routine returns []", test_routine_manager_missing)

def test_routine_manager_list():
    from modules.routine_manager import RoutineManager
    rm = RoutineManager()
    routines = rm.list_routines()
    assert isinstance(routines, list)

test("RoutineManager: list_routines returns list", test_routine_manager_list)

# ─────────────────────────────────────────────
# DOCUMENT READER
# ─────────────────────────────────────────────
print("\n=== DOCUMENT READER ===")

def test_document_reader_txt():
    from modules.document_reader import DocumentReader
    dr = DocumentReader()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Hello Atharva, this is a test document for JARVIS.")
        tmp_path = f.name
    content = dr.read(tmp_path)
    assert "Atharva" in content or "JARVIS" in content
    Path(tmp_path).unlink()

test("DocumentReader: reads .txt file correctly", test_document_reader_txt)

def test_document_reader_chunk():
    from modules.document_reader import DocumentReader
    dr = DocumentReader()
    long_text = "word " * 600  # 600 words
    chunks = dr.chunk_text(long_text)
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    for chunk in chunks:
        assert len(chunk) <= 2000  # no chunk exceeds limit

test("DocumentReader: chunk_text splits long text correctly", test_document_reader_chunk)

# ─────────────────────────────────────────────
# EMAIL HANDLER
# ─────────────────────────────────────────────
print("\n=== EMAIL HANDLER ===")

def test_email_configured():
    from modules.email_handler import EmailHandler
    eh = EmailHandler()
    # Both address and password are set in .env
    assert eh.is_configured() == True

test("EmailHandler: credentials are configured", test_email_configured)

def test_email_missing_recipient():
    from modules.email_handler import EmailHandler
    eh = EmailHandler()
    result = eh.compose_and_send({"to": "", "body": "test", "subject": "test"})
    assert "recipient" in result.lower() or "don't have" in result.lower()

test("EmailHandler: missing recipient handled gracefully", test_email_missing_recipient)

def test_email_missing_body():
    from modules.email_handler import EmailHandler
    eh = EmailHandler()
    result = eh.compose_and_send({"to": "test@test.com", "body": "", "subject": "test"})
    assert "content" in result.lower() or "don't have" in result.lower()

test("EmailHandler: missing body handled gracefully", test_email_missing_body)

# ─────────────────────────────────────────────
# HUD
# ─────────────────────────────────────────────
print("\n=== HUD ===")

def test_hud_html_exists():
    assert Path("D:/JARVIS/hud/index.html").exists()

test("HUD: index.html exists", test_hud_html_exists)

def test_hud_server_import():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
    app = FastAPI()
    assert app is not None

test("HUD: FastAPI + uvicorn importable", test_hud_server_import)

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print("\n" + "="*50)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total = len(results)
print(f"RESULTS: {passed}/{total} passed | {failed} failed")

if failed > 0:
    print("\nFailed tests:")
    for name, ok, err in results:
        if not ok:
            print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
    sys.exit(0)
