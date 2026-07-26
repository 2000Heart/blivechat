(function () {
  'use strict';

  var params = new URLSearchParams(location.search);
  var token = params.get('token') || '';

  var state = { users: {}, animations: {}, global: {} };

  // ------------------------------------------------------------- utilities

  function authHeaders(extra) {
    var h = extra || {};
    h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  async function api(method, path, body) {
    var opts = { method: method, headers: authHeaders({}) };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    var res = await fetch(path, opts);
    var data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      throw new Error((data && data.error) || ('HTTP ' + res.status));
    }
    return data;
  }

  function toast(msg, isError) {
    var el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(function () { el.className = 'toast'; }, 2600);
  }

  function el(id) { return document.getElementById(id); }

  function mediaUrl(filename) { return '/media/' + filename; }

  function typeLabel(t) {
    return t === 'video' ? '视频' : (t === 'gif' ? 'GIF' : '图片');
  }

  // ------------------------------------------------------------- rendering

  function renderOverlayUrl() {
    var url = location.origin + '/overlay?token=' + encodeURIComponent(token);
    el('overlayUrl').value = url;
    el('openOverlay').href = url + '&debug=1';
  }

  function renderGlobal() {
    var g = state.global || {};
    el('globalEnabled').checked = g.enabled !== false;
    el('globalPosition').value = g.position || 'center';
    el('globalSize').value = g.size || 480;
    el('globalCooldown').value = g.defaultCooldownSec != null ? g.defaultCooldownSec : 300;
  }

  function renderAnimationsSelect() {
    var sel = el('userAnimation');
    var current = sel.value;
    sel.innerHTML = '<option value="">（不绑定）</option>';
    Object.keys(state.animations).forEach(function (id) {
      var a = state.animations[id];
      var opt = document.createElement('option');
      opt.value = id;
      opt.textContent = a.name + ' [' + typeLabel(a.type) + ']';
      sel.appendChild(opt);
    });
    sel.value = current;
  }

  function renderAnimations() {
    var wrap = el('animList');
    var ids = Object.keys(state.animations);
    if (ids.length === 0) {
      wrap.innerHTML = '<div class="empty">还没有素材，请先上传。</div>';
      return;
    }
    wrap.innerHTML = '';
    ids.forEach(function (id) {
      var a = state.animations[id];
      var item = document.createElement('div');
      item.className = 'anim-item';

      var preview = a.type === 'video'
        ? '<video src="' + mediaUrl(a.filename) + '" muted loop onmouseover="this.play()" onmouseout="this.pause()"></video>'
        : '<img src="' + mediaUrl(a.filename) + '" alt="">';

      item.innerHTML =
        '<div class="anim-preview">' + preview + '</div>' +
        '<div class="anim-meta">' +
        '<span class="name">' + escapeHtml(a.name) + '</span>' +
        '<span class="tag">' + typeLabel(a.type) + ' · ' + a.durationSec + 's · 音量' + a.volume + '</span>' +
        '<div class="anim-actions">' +
        '<button class="btn small" data-test="' + id + '">测试</button>' +
        '<button class="btn small danger" data-del-anim="' + id + '">删除</button>' +
        '</div></div>';
      wrap.appendChild(item);
    });
  }

  function renderUsers() {
    var tbody = el('userTableBody');
    var ids = Object.keys(state.users);
    if (ids.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">还没有配置用户。</td></tr>';
      return;
    }
    tbody.innerHTML = '';
    ids.forEach(function (uid) {
      var u = state.users[uid];
      var anim = state.animations[u.animationId];
      var animName = anim ? anim.name : '<span class="badge off">未绑定</span>';
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(u.uid) + '</td>' +
        '<td>' + escapeHtml(u.name || '') + '</td>' +
        '<td>' + animName + '</td>' +
        '<td>' + (u.cooldownSec ? u.cooldownSec + 's' : '全局') + '</td>' +
        '<td>' + (u.enabled ? '<span class="badge on">启用</span>' : '<span class="badge off">停用</span>') + '</td>' +
        '<td>' +
        '<button class="btn small" data-edit-user="' + escapeAttr(u.uid) + '">编辑</button> ' +
        '<button class="btn small danger" data-del-user="' + escapeAttr(u.uid) + '">删除</button>' +
        '</td>';
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }

  function renderAll() {
    renderOverlayUrl();
    renderGlobal();
    renderAnimations();
    renderAnimationsSelect();
    renderUsers();
  }

  // --------------------------------------------------------------- actions

  async function loadConfig() {
    var res = await api('GET', '/api/config');
    state = res.data;
    renderAll();
  }

  async function saveGlobal() {
    var body = {
      enabled: el('globalEnabled').checked,
      position: el('globalPosition').value,
      size: parseInt(el('globalSize').value, 10) || 480,
      defaultCooldownSec: parseInt(el('globalCooldown').value, 10) || 0,
    };
    try {
      var res = await api('POST', '/api/global', body);
      state.global = res.data;
      toast('全局设置已保存');
    } catch (e) { toast(e.message, true); }
  }

  async function uploadAnimation(e) {
    e.preventDefault();
    var fileInput = el('animFile');
    if (!fileInput.files.length) { toast('请选择文件', true); return; }
    var fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('name', el('animName').value);
    fd.append('durationSec', el('animDuration').value);
    fd.append('volume', el('animVolume').value);
    try {
      var res = await fetch('/api/animations', {
        method: 'POST', headers: authHeaders({}), body: fd,
      });
      var data = await res.json();
      if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
      state.animations[data.data.id] = data.data;
      el('uploadForm').reset();
      el('animDuration').value = 5;
      el('animVolume').value = 80;
      renderAnimations();
      renderAnimationsSelect();
      toast('素材上传成功');
    } catch (e2) { toast(e2.message, true); }
  }

  async function deleteAnimation(id) {
    if (!confirm('确定删除该素材？绑定它的用户将被解绑。')) return;
    try {
      await api('DELETE', '/api/animations/' + id);
      delete state.animations[id];
      // 刷新用户绑定
      await loadConfig();
      toast('已删除');
    } catch (e) { toast(e.message, true); }
  }

  async function testAnimation(id) {
    try {
      var res = await api('POST', '/api/test', { animationId: id });
      if (res.clients === 0) {
        toast('已触发，但当前没有 OBS 采集页连接。请先在 OBS 或“预览”里打开采集页。', true);
      } else {
        toast('已向 ' + res.clients + ' 个采集页推送测试播放');
      }
    } catch (e) { toast(e.message, true); }
  }

  async function saveUser(e) {
    e.preventDefault();
    var body = {
      uid: el('userUid').value.trim(),
      name: el('userName').value.trim(),
      animationId: el('userAnimation').value,
      cooldownSec: parseInt(el('userCooldown').value, 10) || 0,
      enabled: el('userEnabled').checked,
    };
    if (!body.uid) { toast('请填写用户 UID 或 open_id', true); return; }
    try {
      var res = await api('POST', '/api/users', body);
      state.users[res.data.uid] = res.data;
      resetUserForm();
      renderUsers();
      toast('用户已保存');
    } catch (e2) { toast(e2.message, true); }
  }

  function editUser(uid) {
    var u = state.users[uid];
    if (!u) return;
    el('userUid').value = u.uid;
    el('userName').value = u.name || '';
    el('userAnimation').value = u.animationId || '';
    el('userCooldown').value = u.cooldownSec || 0;
    el('userEnabled').checked = u.enabled !== false;
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }

  async function deleteUser(uid) {
    if (!confirm('确定删除用户 ' + uid + '？')) return;
    try {
      await api('DELETE', '/api/users/' + encodeURIComponent(uid));
      delete state.users[uid];
      renderUsers();
      toast('已删除');
    } catch (e) { toast(e.message, true); }
  }

  function resetUserForm() {
    el('userForm').reset();
    el('userCooldown').value = 0;
    el('userEnabled').checked = true;
  }

  // ---------------------------------------------------------------- events

  function bindEvents() {
    el('saveGlobal').addEventListener('click', saveGlobal);
    el('uploadForm').addEventListener('submit', uploadAnimation);
    el('userForm').addEventListener('submit', saveUser);
    el('userReset').addEventListener('click', resetUserForm);

    el('copyOverlay').addEventListener('click', function () {
      var input = el('overlayUrl');
      input.select();
      navigator.clipboard.writeText(input.value).then(function () {
        toast('已复制 OBS 采集地址');
      }, function () {
        document.execCommand('copy');
        toast('已复制');
      });
    });

    document.addEventListener('click', function (e) {
      var t = e.target;
      if (t.dataset.delAnim) deleteAnimation(t.dataset.delAnim);
      else if (t.dataset.test) testAnimation(t.dataset.test);
      else if (t.dataset.editUser) editUser(t.dataset.editUser);
      else if (t.dataset.delUser) deleteUser(t.dataset.delUser);
    });
  }

  bindEvents();
  loadConfig().catch(function (e) {
    toast('加载失败：' + e.message + '（请确认 URL 中的 token 正确）', true);
  });
})();
