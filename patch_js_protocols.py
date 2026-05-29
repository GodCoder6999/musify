import os
import re

def patch_js(file_path):
    if not os.path.isfile(file_path):
        return
    if not file_path.endswith('.js'):
        return
        
    print(f"Protocol patching {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original = content
        
        # 1. Replace wss templates with ws
        content = content.replace('`wss://${', '`ws://${')
        
        # 2. Replace hardcoded wss:// with ws://
        content = content.replace('wss://', 'ws://')
        
        # 3. Fix the regex check in vendor
        content = content.replace('/^wss:/.test(e.dealer)', '/^ws:/.test(e.dealer)')
        
        # 4. Fix https templates with http
        content = content.replace('`https://${', '`http://${')
        
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Patched {file_path}")
    except Exception as e:
        print(f"Error patching {file_path}: {e}")

for root, dirs, files in os.walk('.'):
    for name in files:
        patch_js(os.path.join(root, name))
