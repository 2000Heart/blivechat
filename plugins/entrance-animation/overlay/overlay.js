(function () {
  'use strict';

  var params = new URLSearchParams(location.search);
  var token = params.get('token') || '';
  var debug = params.get('debug') === '1';

  var stage = document.getElementById('stage');
  var statusEl = document.getElementById('status');

  var queue = [];
  var playing = false;
  var ws = null;
  var reconnectTimer = null;

  function log() {
    if (!debug) return;
    var args = Array.prototype.slice.call(arguments);
    args.unshift('[entrance-overlay]');
    console.log.apply(console, args);
  }

  function setStatus(text) {
    log(text);
    if (debug) {
      statusEl.textContent = text;
    } else {
      statusEl.textContent = '';
    }
  }

  function connect() {
    var proto = location.protocol === 'https:' ? 'wss' : 'ws';
    var url = proto + '://' + location.host + '/ws/overlay?token=' + encodeURIComponent(token);
    ws = new WebSocket(url);

    ws.onopen = function () {
      setStatus('connected');
      log('WebSocket connected:', url);
    };
    ws.onmessage = function (ev) {
      var data;
      try {
        data = JSON.parse(ev.data);
      } catch (e) {
        log('Invalid WebSocket message:', ev.data);
        return;
      }
      log('WebSocket message:', data);
      if (data && data.type === 'play' && data.animation) {
        queue.push(data);
        log('Queued play event, queue length=', queue.length);
        pump();
      }
    };
    ws.onclose = function () {
      setStatus('disconnected, retrying...');
      log('WebSocket closed');
      scheduleReconnect();
    };
    ws.onerror = function (ev) {
      log('WebSocket error:', ev);
      try { ws.close(); } catch (e) {}
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      connect();
    }, 2000);
  }

  function pump() {
    if (playing || queue.length === 0) return;
    var event = queue.shift();
    playing = true;
    playOne(event, function () {
      playing = false;
      pump();
    });
  }

  function applyLayout(wrap, event) {
    var g = event.global || {};
    var pos = g.position || 'center';
    wrap.classList.add('pos-' + pos);
    if (pos !== 'fullscreen') {
      var size = parseInt(g.size, 10) || 480;
      wrap.style.maxWidth = size + 'px';
      wrap.style.maxHeight = size + 'px';
      var media = wrap.querySelector('img, video');
      if (media) {
        media.style.maxWidth = size + 'px';
        media.style.maxHeight = size + 'px';
      }
    }
  }

  function makeCaption(event) {
    var user = event.user || {};
    var name = user.name || '';
    if (!name) return null;
    var cap = document.createElement('div');
    cap.className = 'anim-caption';
    cap.textContent = '欢迎 ' + name + ' 进入直播间';
    return cap;
  }

  function playOne(event, done) {
    var anim = event.animation;
    log('Playing animation:', anim.name || anim.url, 'type=', anim.type, 'user=', (event.user || {}).name);
    var wrap = document.createElement('div');
    wrap.className = 'anim-wrap';

    var finished = false;
    var fallbackTimer = null;

    function finish(reason) {
      if (finished) return;
      finished = true;
      log('Animation finished:', reason || 'unknown', anim.name || anim.url);
      if (fallbackTimer) clearTimeout(fallbackTimer);
      wrap.classList.remove('show');
      setTimeout(function () {
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
        done();
      }, 450);
    }

    var durationMs = (parseFloat(anim.durationSec) || 5) * 1000;

    if (anim.type === 'video') {
      var video = document.createElement('video');
      video.src = anim.url;
      video.autoplay = true;
      video.playsInline = true;
      var vol = parseInt(anim.volume, 10);
      if (isNaN(vol)) vol = 80;
      video.volume = Math.max(0, Math.min(1, vol / 100));
      video.muted = vol <= 0;
      video.addEventListener('ended', function () { finish('ended'); });
      video.addEventListener('error', function () { finish('video-error'); });
      wrap.appendChild(video);
      var cap1 = makeCaption(event);
      if (cap1) wrap.appendChild(cap1);
      stage.appendChild(wrap);
      applyLayout(wrap, event);
      requestAnimationFrame(function () { wrap.classList.add('show'); });
      var p = video.play();
      if (p && p.catch) {
        p.catch(function (err) {
          log('Autoplay blocked, retry muted:', err);
          // 自动播放被拦截时静音重试
          video.muted = true;
          video.play().catch(function () { finish('autoplay-failed'); });
        });
      }
      // 兜底：视频最长播放 durationSec 或其自身时长的较大值由 ended 决定，这里再加安全上限
      fallbackTimer = setTimeout(function () { finish('timeout'); }, Math.max(durationMs, 60000));
    } else {
      var img = document.createElement('img');
      img.src = anim.url;
      img.addEventListener('error', function () { finish('image-error'); });
      wrap.appendChild(img);
      var cap2 = makeCaption(event);
      if (cap2) wrap.appendChild(cap2);
      stage.appendChild(wrap);
      applyLayout(wrap, event);
      requestAnimationFrame(function () { wrap.classList.add('show'); });
      fallbackTimer = setTimeout(function () { finish('timeout'); }, durationMs);
    }
  }

  setStatus('connecting...');
  connect();
})();
