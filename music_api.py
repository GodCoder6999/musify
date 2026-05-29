"""Music backend: metadata/posters (Spotify if creds, else iTunes) + YouTube audio.

Replicates the SoundBound/SpotiFlyer method: a metadata provider supplies
title/artist/cover, and the actual audio stream is resolved from YouTube.

Spotify covers need a token. Set env SPOTIFY_ID / SPOTIFY_SECRET (free app at
developer.spotify.com) to use Spotify's catalog + cover art. Without creds it
falls back to the iTunes Search API (no auth, real album art).
"""
import os
import json
import time
import base64
import urllib.parse
import urllib.request

import store

_TOKEN = {"value": None, "exp": 0}
_SEARCH_CACHE = {}  # query -> (ts, results)
LIKED_COVER = "/misc.scdn.co/liked-songs/liked-songs-300.png"


def _http_json(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _spotify_token():
    cid = os.environ.get("SPOTIFY_ID")
    sec = os.environ.get("SPOTIFY_SECRET")
    if not cid or not sec:
        return None
    if _TOKEN["value"] and _TOKEN["exp"] > time.time():
        return _TOKEN["value"]
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    j = _http_json(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"},
        data=b"grant_type=client_credentials",
    )
    _TOKEN["value"] = j["access_token"]
    _TOKEN["exp"] = time.time() + j.get("expires_in", 3600) - 60
    return _TOKEN["value"]


def search(q, limit=24):
    q = (q or "").strip()
    if not q:
        return []
    tok = _spotify_token()
    if tok:
        j = _http_json(
            "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
                {"q": q, "type": "track", "limit": limit}),
            headers={"Authorization": "Bearer " + tok},
        )
        out = []
        for t in j.get("tracks", {}).get("items", []):
            imgs = t["album"]["images"]
            out.append({
                "id": t["id"],
                "title": t["name"],
                "artist": ", ".join(a["name"] for a in t["artists"]),
                "album": t["album"]["name"],
                "cover": imgs[0]["url"] if imgs else "",
                "duration": t["duration_ms"] // 1000,
                "source": "spotify",
            })
        return out
    # No Spotify creds: iTunes Search API (no auth, real album art).
    j = _http_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": q, "entity": "song", "limit": limit}))
    out = []
    for t in j.get("results", []):
        cover = (t.get("artworkUrl100") or "").replace("100x100bb", "600x600bb")
        out.append({
            "id": str(t.get("trackId")),
            "title": t.get("trackName"),
            "artist": t.get("artistName"),
            "album": t.get("collectionName"),
            "cover": cover,
            "duration": int(t.get("trackTimeMillis", 0)) // 1000,
            "source": "itunes",
        })
    return out


def cached_search(q, limit=12, ttl=3600):
    key = q.lower() + "|" + str(limit)
    hit = _SEARCH_CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    try:
        res = search(q, limit)
    except Exception:
        res = []
    _SEARCH_CACHE[key] = (time.time(), res)
    return res


def _track_item(t):
    return {"kind": "track", "title": t.get("title"), "subtitle": t.get("artist"),
            "cover": t.get("cover"), "track": t}


def home(username):
    """Personalized home: same Spotify-style sections, filled from seeds + activity."""
    u = store.get_user(username) or {"seeds": []}
    seeds = u.get("seeds", [])
    sections = []

    # quick-pick grid: Liked Songs + playlists + recent
    grid = [{"kind": "collection", "title": "Liked Songs", "subtitle": "",
             "cover": LIKED_COVER, "cid": "liked"}]
    for pl in store.playlists(username)[:5]:
        grid.append({"kind": "collection", "title": pl["name"], "subtitle": "Playlist",
                     "cover": pl["cover"], "cid": "playlist:" + pl["id"]})
    for t in store.recent(username, 6):
        grid.append(_track_item(t))
    sections.append({"title": "Good evening, " + username, "type": "grid", "items": grid[:8]})

    # made for user (blend of top seeds)
    if seeds:
        mix = cached_search(" ".join(seeds[:2]), 12)
        if mix:
            sections.append({"title": "Made for " + username, "type": "row",
                             "items": [_track_item(t) for t in mix]})

    # recently played
    rec = store.recent(username, 12)
    if rec:
        sections.append({"title": "Recently played", "type": "row",
                         "items": [_track_item(t) for t in rec]})

    # because you like <seed>
    for seed in seeds[:4]:
        res = cached_search(seed, 10)
        if res:
            sections.append({"title": "Because you like " + seed, "type": "row",
                             "items": [_track_item(t) for t in res]})

    return {"username": username, "seeds": seeds, "sections": sections}


def resolve_stream(query):
    """Resolve a direct YouTube audio URL for 'title artist' via yt-dlp."""
    import yt_dlp
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "noplaylist": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]
        return info.get("url"), info.get("title")
