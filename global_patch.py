import os
import glob

def global_patch():
    # Files to patch: all .js and .html files
    files = glob.glob('**/*.js', recursive=True) + glob.glob('**/*.html', recursive=True)
    
    print(f"Found {len(files)} files to patch.")
    
    for file_path in files:
        if 'server.py' in file_path or 'patch' in file_path:
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            new_content = content
            
            # 1. Dealer protocol check bypass
            new_content = new_content.replace('/^wss:/.test(e.dealer)', 'true')
            new_content = new_content.replace('/^ws:/.test(e.dealer)', 'true')
            
            # 2. Protocol downgrade
            new_content = new_content.replace('wss://', 'ws://')
            # Only replace https:// if it's followed by a spotify domain we handle
            spotify_domains = ['spotify.com', 'scdn.co', 'spotifycdn.com']
            for domain in spotify_domains:
                new_content = new_content.replace(f'https://{domain}', f'http://{domain}')
                new_content = new_content.replace(f'https://api-partner.{domain}', f'http://api-partner.{domain}')
                new_content = new_content.replace(f'https://gae2-spclient.{domain}', f'http://gae2-spclient.{domain}')
            
            # 3. Double protocol fix (from previous session)
            new_content = new_content.replace('ws://ws://', 'ws://')
            new_content = new_content.replace('http://http://', 'http://')
            
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Patched {file_path}")
                
        except Exception as e:
            print(f"Error patching {file_path}: {e}")

if __name__ == '__main__':
    global_patch()
