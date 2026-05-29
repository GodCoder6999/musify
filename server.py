import http.server
import socketserver
import os
import sys
import json
import time
import glob
import hashlib
import base64
import struct
import urllib.parse
import urllib.request

import music_api
import store

WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

# Spotify poster / cover-art CDN hosts that the player loads images from.
IMAGE_HOSTS = (
    'i.scdn.co', 'mosaic.scdn.co', 'image-cdn-ak.spotifycdn.com',
    'image-cdn-fa.spotifycdn.com', 'pickasso.spotifycdn.com', 'misc.scdn.co',
    'seed-mix-image.spotifycdn.com', 'newjams-images.scdn.co',
    'daylist.spotifycdn.com', 'lineup-images.scdn.co', 'thisis-images.scdn.co',
    'dailymix-images.scdn.co', 'wrapped-images.spotifycdn.com',
)


def sniff_image_mime(head):
    if head[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    return None

PORT = int(os.environ.get('PORT', 8000))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

def log(msg):
    with open('server.log', 'a') as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    print(msg)
    sys.stdout.flush()

class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.mjs': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.svg': 'image/svg+xml',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.ico': 'image/x-icon',
        '.webp': 'image/webp',
        '.map': 'application/json',
        '': 'application/octet-stream',
    }

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def _json(self, payload, code=200):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload).encode()
        elif isinstance(payload, str):
            body = payload.encode()
        else:
            body = payload
            
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    # ---- musify auth/session helpers ----
    def _cookie(self, name):
        for part in (self.headers.get('Cookie', '') or '').split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                if k == name:
                    return v
        return None

    def _current_user(self):
        return store.user_for_token(self._cookie('msf_token'))

    def _body(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8', 'ignore'))
        except Exception:
            return {}

    def _json_cookie(self, payload, token=None, expire=False):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        if token:
            self.send_header('Set-Cookie', f'msf_token={token}; Path=/; Max-Age=2592000; SameSite=Lax')
        if expire:
            self.send_header('Set-Cookie', 'msf_token=; Path=/; Max-Age=0')
        self.end_headers()
        self.wfile.write(body)

    def _musify_post(self, path):
        body = self._body()
        if path == '/_m/signup':
            try:
                tok = store.create_user(body.get('username'), body.get('password'), body.get('seeds') or [])
                return self._json_cookie({"ok": True, "user": store.get_user(body.get('username'))}, token=tok)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == '/_m/login':
            if store.verify(body.get('username'), body.get('password')):
                tok = store.new_session(body.get('username'))
                return self._json_cookie({"ok": True, "user": store.get_user(body.get('username'))}, token=tok)
            return self._json({"error": "invalid credentials"}, 401)

        user = self._current_user()
        if not user:
            return self._json({"error": "auth"}, 401)
        if path == '/_m/like':
            store.like(user, body.get('track') or {}); return self._json({"ok": True})
        if path == '/_m/unlike':
            store.unlike(user, body.get('id')); return self._json({"ok": True})
        if path == '/_m/playlist':
            return self._json({"ok": True, "id": store.create_playlist(user, body.get('name'))})
        if path == '/_m/playlist/add':
            store.add_to_playlist(body.get('pid'), body.get('track') or {}); return self._json({"ok": True})
        if path == '/_m/played':
            store.record_played(user, body.get('track') or {}); return self._json({"ok": True})
        return self._json({"error": "unknown"}, 404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        log(f"POST {path}")

        if path.startswith('/_m/'):
            return self._musify_post(path)

        # Handle clienttoken
        if 'clienttoken' in path:
            ct_path = os.path.join(ROOT, 'clienttoken.spotify.com', 'v1', 'clienttoken.json')
            if os.path.isfile(ct_path):
                log(f"Serving clienttoken from {ct_path}")
                with open(ct_path, 'rb') as f:
                    return self._json(f.read())
        
        # Handle events/logging (just say OK)
        if 'events' in path or 'logging' in path:
            return self._json({"status": "ok"})
            
        return self._json({"status": "ok"})

    # ---- minimal WebSocket dealer stub ----
    def _ws_send(self, opcode, data=b''):
        if isinstance(data, str):
            data = data.encode()
        header = bytes([0x80 | opcode])
        n = len(data)
        if n < 126:
            header += bytes([n])
        elif n < 65536:
            header += bytes([126]) + struct.pack('>H', n)
        else:
            header += bytes([127]) + struct.pack('>Q', n)
        self.connection.sendall(header + data)

    def _ws_recv(self):
        h = self.rfile.read(2)
        if len(h) < 2:
            return None
        opcode = h[0] & 0x0F
        masked = h[1] & 0x80
        length = h[1] & 0x7F
        if length == 126:
            length = struct.unpack('>H', self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack('>Q', self.rfile.read(8))[0]
        mask = self.rfile.read(4) if masked else b''
        payload = self.rfile.read(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def handle_ws(self):
        key = self.headers.get('Sec-WebSocket-Key')
        if not key:
            self.send_error(400)
            return
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        super(http.server.SimpleHTTPRequestHandler, self).end_headers()
        log("WS dealer connected")
        # Tell the player it has a dealer connection id so it stops erroring.
        conn_id = 'musify-local-' + base64.b64encode(os.urandom(6)).decode().rstrip('=')
        self._ws_send(0x1, json.dumps({
            "type": "message",
            "method": "PUT",
            "headers": {"Spotify-Connection-Id": conn_id},
            "uri": "hm://pusher/v1/connections/" + conn_id,
        }))
        try:
            while True:
                frame = self._ws_recv()
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:          # close
                    break
                if opcode == 0x9:          # ping -> pong
                    self._ws_send(0xA, payload)
                # ignore client text/binary
        except Exception:
            pass

    def _send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header('Content-type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_image(self, path):
        rel = path.lstrip('/')
        # Snapshot saved cover images with assorted (often wrong) extensions.
        for cand in (rel, rel + '.jpg', rel + '.webp', rel + '.png', rel + '.html', rel + '.jpeg'):
            fp = os.path.join(ROOT, cand)
            if os.path.isfile(fp):
                with open(fp, 'rb') as f:
                    data = f.read()
                ctype = sniff_image_mime(data[:16]) or 'image/jpeg'
                return self._send_bytes(data, ctype)
        # Not in snapshot: fetch live from the real CDN and cache to disk.
        url = 'https://' + rel
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                ctype = r.headers.get('Content-Type') or sniff_image_mime(data[:16]) or 'image/jpeg'
            try:
                fp = os.path.join(ROOT, rel)
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, 'wb') as f:
                    f.write(data)
            except Exception:
                pass
            log(f"img proxied {rel}")
            return self._send_bytes(data, ctype)
        except Exception as e:
            log(f"img fail {rel}: {e}")
            return self.send_error(404)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        # log(f"GET {path}") # Reduced logging for performance

        # 0. WebSocket upgrade (dealer)
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            return self.handle_ws()

        # 0b. Music backend (metadata/posters + YouTube audio)
        if path == '/player':
            self.path = '/player.html'
            return super().do_GET()

        if path == '/_m/search':
            q = urllib.parse.parse_qs(parsed_url.query).get('q', [''])[0]
            try:
                return self._json(music_api.search(q))
            except Exception as e:
                log(f"search err: {e}")
                return self._json({"error": str(e)}, 500)

        if path == '/_m/stream':
            q = urllib.parse.parse_qs(parsed_url.query).get('q', [''])[0]
            try:
                url, _title = music_api.resolve_stream(q)
                if not url:
                    return self._json({"error": "no result"}, 404)
                self.send_response(302)
                self.send_header('Location', url)
                self.end_headers()
                return
            except Exception as e:
                log(f"stream err: {e}")
                return self._json({"error": str(e)}, 500)

        if path == '/_m/me':
            u = self._current_user()
            return self._json({"user": store.get_user(u) if u else None})

        if path == '/_m/logout':
            self.drop = None
            store.drop_session(self._cookie('msf_token'))
            return self._json_cookie({"ok": True}, expire=True)

        if path in ('/_m/home', '/_m/library'):
            u = self._current_user()
            if not u:
                return self._json({"error": "auth"}, 401)
            if path == '/_m/home':
                return self._json(music_api.home(u))
            return self._json({"liked": store.liked(u), "playlists": store.playlists(u),
                               "recent": store.recent(u, 20)})

        # 1. Critical API Stubs
        if path == '/api/server-time':
            return self._json({"serverTime": int(time.time())})
            
        if 'apresolve' in path:
            log(f"Serving apresolve for {path}")
            return self._json({
                "accesspoint": ["http://localhost:8000"],
                "dealer": ["ws://localhost:8000"],
                "spclient": ["http://localhost:8000"],
                "dealer-g2": ["ws://localhost:8000"]
            })

        if path in ('/api/token', '/get_access_token') or path.endswith('/api/token'):
            tok_path = os.path.join(ROOT, 'open.spotify.com', 'api', 'token.json')
            if os.path.isfile(tok_path):
                log(f"Serving token from {tok_path}")
                with open(tok_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data['accessTokenExpirationTimestampMs'] = int((time.time() + 365 * 86400) * 1000)
                return self._json(data)

        # 1b. Poster / cover-art images: serve saved files with correct image
        #     MIME (snapshot saved many as .html), proxy + cache any missing.
        host = path.lstrip('/').split('/', 1)[0]
        if host in IMAGE_HOSTS:
            return self.serve_image(path)

        # 2. Domain Mapping & File Lookup
        possible_roots = [
            '',
            'open.spotify.com',
            'api-partner.spotify.com',
            'gae2-spclient.spotify.com',
            'open.spotifycdn.com',
            'i.scdn.co',
            'encore.scdn.co',
            'image-cdn-ak.spotifycdn.com',
            'pickasso.spotifycdn.com',
            'mosaic.scdn.co'
        ]

        # Try exact path first, then with .json for APIs
        for pr in possible_roots:
            # Clean up the path for local filesystem
            clean_path = path.lstrip('/')
            # Special case for pathfinder/spclient to ensure they look in the right folders
            if 'pathfinder' in clean_path and pr == '': pr = 'api-partner.spotify.com'
            if 'spclient' in clean_path and pr == '': pr = 'gae2-spclient.spotify.com'
            
            full_path = os.path.join(ROOT, pr, clean_path)
            
            # Check for file or file.json
            target = None
            if os.path.isfile(full_path):
                target = full_path
            elif os.path.isfile(full_path + '.json'):
                target = full_path + '.json'
            elif os.path.isfile(full_path + '/query.json'): # Common for pathfinder
                target = full_path + '/query.json'

            if target:
                # log(f"Serving {path} -> {target}")
                self.path = '/' + os.path.relpath(target, ROOT).replace('\\', '/')
                return super().do_GET()

        # 3. Hash Fallback (for files with hashes in names)
        d, name = os.path.split(self.translate_path(path))
        if os.path.isdir(d) and name:
            base_name = name.split('.')[0]
            cands = glob.glob(os.path.join(d, base_name + '*'))
            if cands:
                cands = [c for c in cands if os.path.isfile(c)]
                if cands:
                    # Prefer the one with the same extension if possible
                    ext = os.path.splitext(name)[1]
                    matching_ext = [c for c in cands if c.endswith(ext)]
                    final_target = matching_ext[0] if matching_ext else cands[0]
                    log(f"Fallback {path} -> {os.path.basename(final_target)}")
                    self.path = '/' + os.path.relpath(final_target, ROOT).replace('\\', '/')
                    return super().do_GET()

        # 4. SPA Fallback (Only for non-asset, non-API paths)
        if not os.path.splitext(path)[1] and not any(
            x in path for x in ('api', 'spclient', 'pathfinder', 'clienttoken', 'image', 'cdn', 'events')
        ):
            log(f"SPA Fallback {path} -> index.html")
            self.path = '/index.html'
            return super().do_GET()

        # 5. Root / Fallback  (content index = populated, styled offline)
        if path in ('/', '/index.html'):
            self.path = '/index.html'
            return super().do_GET()

        log(f"404 {path}")
        self.send_error(404)

class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == '__main__':
    with open('server.log', 'w') as f:
        f.write(f"{time.strftime('%H:%M:%S')} musify started\n")
    store.init_db()
    with ThreadingServer(("", PORT), Handler) as httpd:
        log(f"Server started on http://localhost:{PORT}")
        httpd.serve_forever()
