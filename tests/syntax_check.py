import ast

files = [
    'D:/JARVIS/modules/tts.py',
    'D:/JARVIS/modules/stt.py',
    'D:/JARVIS/modules/intent.py',
    'D:/JARVIS/modules/automation.py',
    'D:/JARVIS/modules/vision.py',
    'D:/JARVIS/modules/scheduler.py',
    'D:/JARVIS/modules/memory.py',
    'D:/JARVIS/modules/long_term_memory.py',
    'D:/JARVIS/modules/sentiment.py',
    'D:/JARVIS/modules/powershell_handler.py',
    'D:/JARVIS/modules/routine_manager.py',
    'D:/JARVIS/modules/web_search.py',
    'D:/JARVIS/modules/email_handler.py',
    'D:/JARVIS/config.py',
]

all_ok = True
for f in files:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        name = f.split('/')[-1]
        print(f'OK: {name}')
    except SyntaxError as e:
        print(f'SYNTAX ERROR in {f}: {e}')
        all_ok = False

if all_ok:
    print('All modules: PASSED')
else:
    print('SOME MODULES FAILED')
