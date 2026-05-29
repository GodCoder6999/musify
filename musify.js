/* musify: login/signup gate for personalization, then keep the Spotify rip's
   UI/text/layout untouched EXCEPT: swap cover posters, set the avatar initial,
   and replace the sidebar library with the user's own (Liked Songs + playlists
   they create). Also keeps search->modal->YouTube-audio + like / create. */
(function () {
  'use strict';
  if (window.__musify) return;
  window.__musify = true;

  var SEED_PRESETS = ['Arijit Singh', 'Ed Sheeran', 'Taylor Swift', 'The Weeknd',
    'Drake', 'A.R. Rahman', 'Imagine Dragons', 'Coldplay', 'Pritam', 'Bollywood',
    'Pop', 'Lo-fi', 'Punjabi', 'Rock', 'Honey Singh', 'Diljit Dosanjh'];
  var SEARCH = '/_m/search?q=', STREAM = '/_m/stream?q=';
  var HEART = '<svg width="20" height="20" viewBox="0 0 24 24" fill="#fff"><path d="M12 21s-7-4.5-9.5-8.5C.5 9 2.5 5.5 6 5.5c2 0 3.2 1.2 4 2.3.8-1.1 2-2.3 4-2.3 3.5 0 5.5 3.5 3.5 7C19 16.5 12 21 12 21z"/></svg>';

  function spotifyLogo(s) { return '<svg viewBox="0 0 168 168" width="' + s + '" height="' + s + '"><path fill="#1ed760" d="M83.996.277C37.747.277.253 37.77.253 84.019c0 46.251 37.494 83.741 83.743 83.741 46.254 0 83.744-37.49 83.744-83.741 0-46.246-37.49-83.738-83.745-83.738l.001-.004zm38.404 120.78a5.217 5.217 0 01-7.18 1.73c-19.662-12.01-44.414-14.73-73.564-8.07a5.222 5.222 0 01-6.249-3.93 5.213 5.213 0 013.926-6.25c31.9-7.291 59.263-4.15 81.337 9.34 2.46 1.51 3.24 4.72 1.73 7.18zm10.25-22.805c-1.89 3.075-5.91 4.045-8.98 2.155-22.51-13.839-56.823-17.846-83.448-9.764-3.453 1.043-7.1-.903-8.148-4.35a6.538 6.538 0 014.354-8.143c30.413-9.228 68.222-4.758 94.072 11.127 3.07 1.89 4.04 5.91 2.15 8.976v-.001zm.88-23.744c-26.99-16.031-71.52-17.505-97.289-9.684-4.138 1.255-8.514-1.082-9.768-5.22a7.835 7.835 0 015.221-9.771c29.581-8.98 78.756-7.245 109.83 11.202a7.823 7.823 0 012.74 10.733c-2.2 3.722-7.02 4.949-10.73 2.74h-.004z"/></svg>'; }
  var esc = function (s) { return (s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var fmt = function (s) { s = Math.floor(s || 0); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  var getJSON = function (u) { return fetch(u).then(function (r) { return r.json(); }); };
  var postJSON = function (u, b) { return fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then(function (r) { return r.json(); }); };
  var g = function (id) { return document.getElementById(id); };

  var USER = null, LIKED = {}, LIKED_TRACKS = [], PLAYLISTS = [], POOL = [], _idc = 0;
  var UI = {};
  var audio = document.createElement('audio'); audio.id = 'musify-audio'; document.documentElement.appendChild(audio);

  // ===================== AUTH GATE =====================
  var auth = document.createElement('div'); auth.id = 'msf-auth';
  document.body.appendChild(auth);
  var authMode = 'login';
  function showAuth() {
    var sel = {};
    auth.innerHTML =
      '<div class="card"><div class="logo">' + spotifyLogo(40) + '<span>Spotify</span></div>' +
      '<div class="sub">' + (authMode === 'login' ? 'Log in to continue' : 'Sign up — pick a few favorites to personalize') + '</div>' +
      '<label>Username</label><input type="text" id="msf-u" autocomplete="username">' +
      '<label>Password</label><input type="password" id="msf-p" autocomplete="current-password">' +
      (authMode === 'signup' ? '<label>Favorite artists / genres</label><div id="msf-seeds"></div>' : '') +
      '<button class="go">' + (authMode === 'login' ? 'Log In' : 'Sign Up') + '</button>' +
      '<div class="err" id="msf-err"></div>' +
      '<div class="switch">' + (authMode === 'login' ? 'No account? <a id="msf-sw">Sign up</a>' : 'Have an account? <a id="msf-sw">Log in</a>') + '</div></div>';
    auth.classList.add('show');
    if (authMode === 'signup') {
      var box = auth.querySelector('#msf-seeds');
      SEED_PRESETS.forEach(function (s) {
        var c = document.createElement('span'); c.className = 'chip'; c.textContent = s;
        c.onclick = function () { c.classList.toggle('on'); sel[s] = c.classList.contains('on'); };
        box.appendChild(c);
      });
    }
    auth.querySelector('#msf-sw').onclick = function () { authMode = authMode === 'login' ? 'signup' : 'login'; showAuth(); };
    auth.querySelector('.go').onclick = function () {
      var u = auth.querySelector('#msf-u').value.trim(), p = auth.querySelector('#msf-p').value;
      var seeds = Object.keys(sel).filter(function (k) { return sel[k]; });
      postJSON(authMode === 'login' ? '/_m/login' : '/_m/signup', { username: u, password: p, seeds: seeds }).then(function (d) {
        if (d.error) { auth.querySelector('#msf-err').textContent = d.error; return; }
        auth.classList.remove('show'); initApp(d.user);
      });
    };
    auth.querySelector('#msf-u').addEventListener('keydown', function (e) { if (e.key === 'Enter') auth.querySelector('#msf-p').focus(); });
    auth.querySelector('#msf-p').addEventListener('keydown', function (e) { if (e.key === 'Enter') auth.querySelector('.go').click(); });
  }

  // ===================== SEARCH MODAL + PLAYER =====================
  var built = false;
  function buildSearchLayer() {
    var backdrop = document.createElement('div'); backdrop.id = 'msf-backdrop';
    var panel = document.createElement('div'); panel.id = 'msf-panel';
    panel.innerHTML = '<div id="msf-head"><div class="ttl">Search</div><button class="x" title="Close">&times;</button></div><div id="msf-results"></div>';
    document.body.appendChild(backdrop); document.body.appendChild(panel);
    var results = panel.querySelector('#msf-results');
    UI.show = function () { panel.classList.add('open'); backdrop.classList.add('open'); };
    UI.hide = function () { panel.classList.remove('open'); backdrop.classList.remove('open'); };
    UI.setTitle = function (t) { panel.querySelector('.ttl').textContent = t; };
    panel.querySelector('.x').onclick = UI.hide; backdrop.onclick = UI.hide;

    var bar = document.createElement('div'); bar.id = 'msf-bar';
    bar.innerHTML =
      '<div class="np"><img id="msf-img" alt=""><div style="min-width:0"><div class="t" id="msf-t">—</div><div class="a" id="msf-a"></div></div><button class="msf-bheart" id="msf-bheart" title="Like">♡</button></div>' +
      '<div class="ctr"><div class="btns">' +
      '<button class="ic" id="msf-sh" title="Shuffle"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M14 4h6v6h-2V7.4l-9.3 9.3-1.4-1.4L16.6 6H14zM4 6h4l3 3-1.5 1.5L7 8H4zm13.5 8.5L20 17v-3h-2v.6l-1.5-1.5zM4 16h3l9.3-9.3 1.4 1.4L8 18H4z"/></svg></button>' +
      '<button class="ic" id="msf-pv" title="Previous"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M7 6h2v12H7zM20 6v12l-9-6z"/></svg></button>' +
      '<button class="pp" id="msf-pp"><svg id="msf-ppi" width="18" height="18" viewBox="0 0 24 24" fill="#000"><path d="M8 5v14l11-7z"/></svg></button>' +
      '<button class="ic" id="msf-nx" title="Next"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M15 6h2v12h-2zM4 6l9 6-9 6z"/></svg></button>' +
      '<button class="ic" id="msf-rp" title="Repeat"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M7 7h10v3l4-4-4-4v3H5v6h2zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2z"/></svg></button></div>' +
      '<div class="seek"><span class="tm" id="msf-cur">0:00</span><input type="range" id="msf-seek" min="0" max="1000" value="0"><span class="tm" id="msf-dur">0:00</span></div></div>' +
      '<div class="vol"><svg width="16" height="16" viewBox="0 0 24 24" fill="#b3b3b3"><path d="M3 10v4h4l5 5V5L7 10H3z"/></svg><input type="range" id="msf-vol" min="0" max="1" step="0.01" value="1"></div>';
    document.body.appendChild(bar);
    bar.classList.add('show');   // always visible, covers the rip's dead player bar

    g('msf-pp').onclick = function () { audio.paused ? audio.play() : audio.pause(); };
    function setPP(p) { g('msf-ppi').innerHTML = p ? '<path d="M6 5h4v14H6zM14 5h4v14h-4z"/>' : '<path d="M8 5v14l11-7z"/>'; }
    audio.onplay = function () { setPP(true); }; audio.onpause = function () { setPP(false); };
    audio.ontimeupdate = function () { g('msf-cur').textContent = fmt(audio.currentTime); if (audio.duration) { g('msf-seek').value = (audio.currentTime / audio.duration) * 1000; g('msf-dur').textContent = fmt(audio.duration); } };
    g('msf-seek').oninput = function () { if (audio.duration) audio.currentTime = (+this.value / 1000) * audio.duration; };
    g('msf-vol').oninput = function () { audio.volume = +this.value; };

    var Q = [], QI = 0;
    function _play() {
      var it = Q[QI]; if (!it) return;
      g('msf-img').src = it.cover || ''; g('msf-t').textContent = it.title; g('msf-a').textContent = it.artist + '  •  resolving…';
      bar.classList.add('show');
      var bh = g('msf-bheart'); bh.className = 'msf-bheart' + (LIKED[it.id] ? ' on' : ''); bh.innerHTML = LIKED[it.id] ? HEART : '♡';
      bh.onclick = function () { toggleLike(it, bh); };
      audio.src = STREAM + encodeURIComponent((it.title + ' ' + it.artist).trim());
      audio.play().then(function () { g('msf-a').textContent = it.artist; }).catch(function (e) { g('msf-a').textContent = it.artist + '  •  ' + e.message; });
    }
    var shuffle = false, repeat = false;
    function nextTrack() { if (!Q.length) return; QI = shuffle ? Math.floor(Math.random() * Q.length) : (QI + 1) % Q.length; _play(); }
    function prevTrack() { if (audio.currentTime > 3) { audio.currentTime = 0; return; } QI = (QI - 1 + Q.length) % Q.length; _play(); }
    audio.onended = function () { if (repeat) { audio.currentTime = 0; audio.play(); } else if (Q.length > 1) nextTrack(); };
    g('msf-nx').onclick = nextTrack;
    g('msf-pv').onclick = prevTrack;
    g('msf-sh').onclick = function () { shuffle = !shuffle; g('msf-sh').classList.toggle('on', shuffle); };
    g('msf-rp').onclick = function () { repeat = !repeat; g('msf-rp').classList.toggle('on', repeat); };
    UI.play = function (it) { Q = [it]; QI = 0; _play(); };
    UI.playList = function (list, idx) { Q = list.slice(); QI = idx || 0; _play(); };
    UI.render = function (items) {
      results.innerHTML = '';
      if (!items.length) { results.innerHTML = '<div class="msf-msg">No results.</div>'; return; }
      items.forEach(function (it) {
        var c = document.createElement('div'); c.className = 'msf-card';
        c.innerHTML = '<img src="' + esc(it.cover) + '" onerror="this.style.visibility=\'hidden\'"><div class="pb"><svg width="20" height="20" viewBox="0 0 24 24" fill="#000"><path d="M8 5v14l11-7z"/></svg></div>' +
          '<div class="t">' + esc(it.title) + '</div><div class="a">' + esc(it.artist) + '</div>' +
          '<div class="msf-cardacts"><button class="lk' + (LIKED[it.id] ? ' on' : '') + '" title="Like">' + (LIKED[it.id] ? '♥' : '♡') + '</button>' +
          '<button class="ad" title="Add to playlist">+</button></div>';
        c.onclick = function () { UI.play(it); };
        var lk = c.querySelector('.lk'); lk.onclick = function (e) { e.stopPropagation(); toggleLike(it, lk); };
        c.querySelector('.ad').onclick = function (e) { e.stopPropagation(); addToPlaylist(it); };
        results.appendChild(c);
      });
    };
    UI.doSearch = function (q) {
      UI.setTitle('Results for "' + q + '"'); results.innerHTML = '<div class="msf-msg">Searching…</div>'; UI.show();
      getJSON(SEARCH + encodeURIComponent(q)).then(function (d) { UI.render(d.error ? [] : d); }).catch(function (e) { results.innerHTML = '<div class="msf-msg">Error: ' + e.message + '</div>'; });
    };

    function hook() {
      var inp = document.querySelector('input[data-testid="search-input"]');
      if (inp && !inp.__msf) { inp.__msf = true; inp.addEventListener('keydown', function (e) { if (e.key === 'Enter' && inp.value.trim()) { e.preventDefault(); e.stopImmediatePropagation(); UI.doSearch(inp.value.trim()); } }, true); }
    }
    setInterval(hook, 800);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') UI.hide(); });
  }

  // ===================== LIKE / PLAYLIST =====================
  function toggleLike(it, btn) {
    if (LIKED[it.id]) postJSON('/_m/unlike', { id: it.id }).then(function () { delete LIKED[it.id]; markLike(btn, false); refreshLibrary(); });
    else postJSON('/_m/like', { track: it }).then(function () { LIKED[it.id] = 1; markLike(btn, true); refreshLibrary(); });
  }
  function markLike(btn, on) { if (!btn) return; var bar = btn.id === 'msf-bheart'; btn.className = (bar ? 'msf-bheart' : 'lk') + (on ? ' on' : ''); btn.innerHTML = on ? (bar ? HEART : '♥') : '♡'; }
  function addToPlaylist(it) {
    var names = PLAYLISTS.map(function (p) { return p.name; });
    var ans = prompt('Add "' + it.title + '" to playlist:\n' + (names.length ? names.join(', ') + '\n' : '') + 'Type an existing or new name:');
    if (!ans) return;
    var pl = PLAYLISTS.filter(function (p) { return p.name.toLowerCase() === ans.toLowerCase(); })[0];
    if (pl) postJSON('/_m/playlist/add', { pid: pl.id, track: it }).then(refreshLibrary);
    else postJSON('/_m/playlist', { name: ans }).then(function (r) { postJSON('/_m/playlist/add', { pid: r.id, track: it }).then(refreshLibrary); });
  }

  // ===================== AVATAR + SIDEBAR LIBRARY =====================
  function setAvatar() {
    if (!USER) return;
    var s = document.querySelector('[data-testid="username-first-letter"]');
    if (s) s.textContent = (USER.username[0] || '?').toUpperCase();
  }

  function personalizeLibrary() {
    var area = document.querySelector('[aria-label="Your Library"]');
    if (!area) return;
    var rows = [].slice.call(area.querySelectorAll('[role="row"]'));
    if (!rows.length) return;
    rows.forEach(function (r) { if (!r.__msfMine) r.style.display = 'none'; });   // hide rip's Anirban playlists
    var parent = rows[0].parentElement;
    var box = parent.querySelector('#msf-lib');
    if (!box) { box = document.createElement('div'); box.id = 'msf-lib'; parent.appendChild(box); }
    var sig = LIKED_TRACKS.length + '|' + PLAYLISTS.map(function (p) { return p.id + ':' + p.tracks.length; }).join(',');
    if (box.__sig === sig && box.firstChild) return;   // unchanged -> skip rebuild (avoids click churn)
    box.__sig = sig;
    var html = '<div class="msf-li" data-c="liked"><div class="ph liked">' + HEART + '</div>' +
      '<div style="min-width:0"><div class="nm">Liked Songs</div><div class="mt">Playlist • ' + LIKED_TRACKS.length + ' songs</div></div></div>';
    PLAYLISTS.forEach(function (p) {
      html += '<div class="msf-li" data-c="playlist:' + p.id + '">' +
        (p.cover ? '<img src="' + esc(p.cover) + '">' : '<div class="ph"></div>') +
        '<div style="min-width:0"><div class="nm">' + esc(p.name) + '</div><div class="mt">Playlist • ' + p.tracks.length + ' songs</div></div></div>';
    });
    box.innerHTML = html;
    [].forEach.call(box.querySelectorAll('.msf-li'), function (el) {
      el.onclick = function () { openCollection(el.getAttribute('data-c')); };
    });
  }

  function openCollection(cid) {
    var owner = USER ? USER.username : '';
    if (cid === 'liked') renderPlaylistView('Liked Songs', owner, LIKED_TRACKS);
    else if (cid.indexOf('playlist:') === 0) {
      var id = cid.split(':')[1], pl = PLAYLISTS.filter(function (p) { return p.id === id; })[0];
      renderPlaylistView(pl ? pl.name : 'Playlist', owner, pl ? pl.tracks : []);
    }
  }

  // full-center playlist page (like the rip's playlist view)
  var CLOCK = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#b3b3b3" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
  function ensureView() {
    var v = g('msf-view');
    if (!v) {
      v = document.createElement('div'); v.id = 'msf-view';
      v.innerHTML = '<button class="back" title="Back">&lsaquo;</button><div class="scroll"></div>';
      document.body.appendChild(v);
      v.querySelector('.back').onclick = function () { v.classList.remove('open'); };
      window.addEventListener('resize', function () { if (v.classList.contains('open')) positionView(v); });
    }
    return v;
  }
  function positionView(v) {
    var sideEl = document.querySelector('[aria-label="Your Library"]');
    var side = sideEl ? sideEl.getBoundingClientRect() : null;
    var npb = document.querySelector('[data-testid="now-playing-bar"]');
    var bottomY = npb ? npb.getBoundingClientRect().top : (window.innerHeight - 96);
    var rp = [].slice.call(document.querySelectorAll('*')).filter(function (e) {
      return /About the/.test(e.innerText || '') && e.getBoundingClientRect().left > window.innerWidth * 0.6;
    })[0];
    var rightX = rp ? rp.getBoundingClientRect().left : (window.innerWidth - 348);
    var left = side ? side.right + 8 : 548;
    v.style.left = left + 'px';
    v.style.top = '76px';
    v.style.width = Math.max(320, (rightX - 8) - left) + 'px';
    v.style.height = (bottomY - 76 - 8) + 'px';
  }
  function renderPlaylistView(title, owner, tracks) {
    var v = ensureView(), sc = v.querySelector('.scroll');
    var cover = (tracks[0] && tracks[0].cover) || POOL[0] || '';
    var dur = tracks.reduce(function (a, t) { return a + (t.duration || 0); }, 0);
    var h = '<div class="hd"><img src="' + esc(cover) + '" onerror="this.style.visibility=\'hidden\'">' +
      '<div><div class="lbl">Public Playlist</div><h1>' + esc(title) + '</h1>' +
      '<div class="sub"><b>' + esc(owner) + '</b> • ' + tracks.length + ' songs' + (dur ? ', about ' + Math.round(dur / 60) + ' min' : '') + '</div></div></div>' +
      '<div class="ctrls"><button class="bigplay"><svg width="24" height="24" viewBox="0 0 24 24" fill="#000"><path d="M8 5v14l11-7z"/></svg></button></div>' +
      '<div class="thead"><span class="ix">#</span><span>Title</span><span>Album</span><span class="du">' + CLOCK + '</span></div>';
    if (!tracks.length) h += '<div class="empty">No songs yet — search and like songs (or add to this playlist) to fill it.</div>';
    tracks.forEach(function (t, i) {
      h += '<div class="trow" data-i="' + i + '"><span class="ix">' + (i + 1) + '</span>' +
        '<span class="ti"><img src="' + esc(t.cover) + '" onerror="this.style.visibility=\'hidden\'"><span style="min-width:0"><span class="t">' + esc(t.title) + '</span><span class="a">' + esc(t.artist) + '</span></span></span>' +
        '<span class="al">' + esc(t.album || '') + '</span><span class="du">' + fmt(t.duration || 0) + '</span></div>';
    });
    sc.innerHTML = h; sc.scrollTop = 0;
    sc.querySelector('.bigplay').onclick = function () { if (tracks.length) UI.playList(tracks, 0); };
    [].forEach.call(sc.querySelectorAll('.trow'), function (row) { var i = +row.getAttribute('data-i'); row.onclick = function () { UI.playList(tracks, i); }; });
    positionView(v); v.classList.add('open');
  }

  function hookCreate() {
    [].forEach.call(document.querySelectorAll('button'), function (b) {
      if (b.__msfCreate) return;
      if (/^\s*\+?\s*Create\s*$/i.test(b.innerText || '')) {
        b.__msfCreate = true;
        b.addEventListener('click', function (e) {
          e.preventDefault(); e.stopImmediatePropagation();
          var n = prompt('Playlist name:'); if (n) postJSON('/_m/playlist', { name: n }).then(refreshLibrary);
        }, true);
      }
    });
  }

  function refreshLibrary() {
    return getJSON('/_m/library').then(function (d) {
      LIKED = {}; LIKED_TRACKS = d.liked || []; LIKED_TRACKS.forEach(function (t) { LIKED[t.id] = 1; });
      PLAYLISTS = d.playlists || [];
      personalizeLibrary();
    });
  }

  // ===================== CENTER: kill Anirban, use the user =====================
  function findQuickGrid() {
    var hits = [].slice.call(document.querySelectorAll('*')).filter(function (e) {
      return /^Liked Songs$/.test((e.innerText || '').trim()) && e.children.length <= 1;
    });
    var t = hits.filter(function (e) { var b = e.getBoundingClientRect(); return b.top < 420 && b.left > 460 && b.width > 0; })[0];
    if (!t) return null;
    var el = t;
    while (el && el.children.length < 4) el = el.parentElement;
    return (el && el.children.length >= 4 && el.children.length <= 12) ? el : null;
  }
  function relabelQuickGrid() {
    var grid = findQuickGrid(); if (!grid) return;
    var tiles = [].slice.call(grid.children);
    var items = [{ name: 'Liked Songs', cid: 'liked' }].concat(PLAYLISTS.map(function (p) { return { name: p.name, cid: 'playlist:' + p.id }; }));
    tiles.forEach(function (tile, i) {
      if (i >= items.length) { tile.style.display = 'none'; tile.__msfItem = null; return; }
      tile.style.display = '';
      tile.__msfItem = items[i];                 // live ref (fixes stale-closure: some tiles not opening)
      var leaf = [].slice.call(tile.querySelectorAll('*')).filter(function (e) { return e.children.length === 0 && (e.innerText || '').trim().length > 0; })[0];
      if (leaf && leaf.textContent !== items[i].name) leaf.textContent = items[i].name;
      if (!tile.__msfQ) { tile.__msfQ = true; tile.addEventListener('click', function (e) { e.preventDefault(); e.stopImmediatePropagation(); if (tile.__msfItem) openCollection(tile.__msfItem.cid); }, true); }
    });
  }
  function replaceAnirban() {
    if (!USER) return;
    var name = USER.username;
    var walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    var nodes = [], n;
    while ((n = walk.nextNode())) {
      if (/Anirban/.test(n.nodeValue) && !(n.parentElement && n.parentElement.closest('#msf-lib,#msf-panel,#msf-bar,#msf-auth'))) nodes.push(n);
    }
    nodes.forEach(function (nd) { nd.nodeValue = nd.nodeValue.replace(/Anirban Bose/g, name).replace(/Anirban/g, name); });
  }
  function personalizeCenter() { relabelQuickGrid(); replaceAnirban(); }

  // ===================== POSTER SWAP =====================
  function isOurs(el) { return el.closest && (el.closest('#msf-panel') || el.closest('#msf-bar') || el.closest('#msf-auth') || el.closest('#msf-lib')); }
  function swapPosters() {
    if (!POOL.length) return;
    [].forEach.call(document.images, function (img) {
      if (isOurs(img)) return;
      var w = img.clientWidth, h = img.clientHeight;
      if (w < 40 || Math.abs(w - h) > 6) return;
      var id = img.getAttribute('data-msf-id');
      if (!id) { id = String(_idc++); img.setAttribute('data-msf-id', id); }
      var pick = POOL[(+id) % POOL.length];
      if (img.getAttribute('srcset')) img.setAttribute('srcset', '');
      if (img.src !== pick) img.src = pick;
    });
  }
  function personalizePosters(seeds) {
    var qs = (seeds && seeds.length) ? seeds : ['top hits'];
    Promise.all(qs.map(function (s) { return getJSON(SEARCH + encodeURIComponent(s)).catch(function () { return []; }); }))
      .then(function (lists) {
        POOL = []; lists.forEach(function (l) { (l || []).forEach(function (t) { if (t.cover) POOL.push(t.cover); }); });
        swapPosters();
      });
  }

  // ===================== orchestration =====================
  var _t = null;
  function reapply() {
    if (_t) return;
    _t = setTimeout(function () { _t = null; setAvatar(); personalizeLibrary(); hookCreate(); personalizeCenter(); swapPosters(); }, 200);
  }
  function initApp(user) {
    USER = user;
    if (!built) { buildSearchLayer(); built = true; }
    setAvatar(); hookCreate();
    refreshLibrary();
    personalizePosters(user && user.seeds ? user.seeds : []);
    new MutationObserver(reapply).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'srcset'] });
    setInterval(function () { setAvatar(); personalizeLibrary(); personalizeCenter(); swapPosters(); }, 1500);
  }

  getJSON('/_m/me').then(function (d) { if (d.user) initApp(d.user); else showAuth(); }).catch(showAuth);
  console.log('[musify] gate + personalization active');
})();
