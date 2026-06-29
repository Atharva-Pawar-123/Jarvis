"""JARVIS Upgrade Verification Suite"""
import time
import sys
sys.path.insert(0, ".")

# ── TEST 1: Ollama Connectivity ──
print("=" * 50)
print("TEST 1: Ollama Connectivity & GPU")
print("=" * 50)
try:
    import ollama
    start = time.time()
    r = ollama.chat(model='qwen2.5:1.5b', messages=[{'role':'user','content':'Say: test passed.'}])
    msg = r["message"]["content"]
    elapsed = time.time() - start
    print(f"  Response: {msg}")
    print(f"  Time: {elapsed:.2f}s")
    eval_count = r.get("eval_count", 0)
    eval_dur = r.get("eval_duration", 1)
    if eval_dur > 0:
        tps = eval_count / (eval_dur / 1e9)
        print(f"  Tokens/sec: {tps:.1f}")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 2: Config Loads Without Gemini ──
print("\n" + "=" * 50)
print("TEST 2: Config Loads (No Gemini)")
print("=" * 50)
try:
    import config
    assert hasattr(config, 'PRIMARY_MODEL')
    assert hasattr(config, 'JARVIS_SYSTEM_PROMPT')
    assert 'gemini' not in config.PRIMARY_MODEL.lower()
    print(f"  PRIMARY_MODEL: {config.PRIMARY_MODEL}")
    print(f"  FAST_MODEL: {config.FAST_MODEL}")
    print(f"  CODER_MODEL: {config.CODER_MODEL}")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 3: LLM Engine Imports ──
print("\n" + "=" * 50)
print("TEST 3: LLM Engine Import")
print("=" * 50)
try:
    from modules.llm import IntelligentLLMEngine
    print("  IntelligentLLMEngine imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 4: TTS Engine Import ──
print("\n" + "=" * 50)
print("TEST 4: Streaming TTS Import")
print("=" * 50)
try:
    from modules.tts import StreamingTextToSpeech
    print("  StreamingTextToSpeech imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 5: Intent Classifier Import ──
print("\n" + "=" * 50)
print("TEST 5: Intent Classifier Import")
print("=" * 50)
try:
    from modules.intent import DualModelIntentClassifier
    print("  DualModelIntentClassifier imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 6: Hybrid RAG Memory Import ──
print("\n" + "=" * 50)
print("TEST 6: Hybrid RAG Memory Import")
print("=" * 50)
try:
    from modules.long_term_memory import HybridRAGMemory
    print("  HybridRAGMemory imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 7: ReAct Agent Import ──
print("\n" + "=" * 50)
print("TEST 7: ReAct Agent Import")
print("=" * 50)
try:
    from modules.react_agent import ReActAgent
    print("  ReActAgent imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 8: UltraPlan Import ──
print("\n" + "=" * 50)
print("TEST 8: UltraPlan Import")
print("=" * 50)
try:
    from modules.ultraplan import UltraPlanCoordinator
    print("  UltraPlanCoordinator imported successfully.")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL - {e}")

# ── TEST 9: No Gemini in codebase ──
print("\n" + "=" * 50)
print("TEST 9: Zero Gemini Imports in Modules")
print("=" * 50)
import os
found_gemini = False
for root, dirs, files in os.walk("modules"):
    for fname in files:
        if fname.endswith(".py"):
            fpath = os.path.join(root, fname)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if 'google.generativeai' in content or 'import genai' in content:
                print(f"  FOUND Gemini reference in: {fpath}")
                found_gemini = True
if not found_gemini:
    print("  No Gemini imports found in any module.")
    print("  RESULT: PASS")
else:
    print("  RESULT: FAIL")

print("\n" + "=" * 50)
print("ALL VERIFICATION TESTS COMPLETE")
print("=" * 50)
