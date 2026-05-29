import os

def debug_js(file_path):
    if not os.path.isfile(file_path):
        return
    if 'vendor' not in file_path:
        return
        
    print(f"Adding debug log to {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original = content
        content = content.replace('/^ws:/.test(e.dealer)', '(console.log("DEALER_DEBUG:", e.dealer),/^ws:/.test(e.dealer))')
        
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Debug added to {file_path}")
    except Exception as e:
        print(f"Error adding debug to {file_path}: {e}")

for root, dirs, files in os.walk('.'):
    for name in files:
        debug_js(os.path.join(root, name))
