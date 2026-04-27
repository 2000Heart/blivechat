(function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";
  let roomKey = "all";
  let ws = null;

  const roomKeyInput = document.getElementById("roomKeyInput");
  const queueMeta = document.getElementById("queueMeta");
  const queueTableBody = document.getElementById("queueTableBody");
  const overlayUrlEl = document.getElementById("overlayUrl");

  function apiUrl(path) {
    const sep = path.includes("?") ? "&" : "?";
    return `${path}${sep}token=${encodeURIComponent(token)}`;
  }

  function renderQueue(queue) {
    queueMeta.textContent = `roomKey=${queue.roomKey} version=${queue.version} size=${queue.size}`;
    queueTableBody.innerHTML = "";
    queue.items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${item.rank}</td><td>${item.authorName}</td><td>${item.giftTotalValue}</td><td>${item.joinTimestamp}</td><td>${item.userKey}</td>`;
      queueTableBody.appendChild(tr);
    });
  }

  async function fetchQueue() {
    const rsp = await fetch(apiUrl(`/api/queue?roomKey=${encodeURIComponent(roomKey)}`));
    const data = await rsp.json();
    if (data.ok) renderQueue(data.queue);
  }

  async function fetchSettings() {
    const rsp = await fetch(apiUrl("/api/settings"));
    const data = await rsp.json();
    if (!data.ok) return;
    const s = data.settings;
    document.getElementById("requireFansMedal").checked = !!s.requireFansMedal;
    document.getElementById("minFansLevel").value = s.minFansLevel;
    document.getElementById("requireGuard").checked = !!s.requireGuard;
    document.getElementById("minGuardLevel").value = s.minGuardLevel;
    document.getElementById("maxQueueSize").value = s.maxQueueSize;
    const origin = window.location.origin;
    overlayUrlEl.textContent = `${origin}/overlay.html?token=${token}&roomKey=${encodeURIComponent(roomKey)}`;
  }

  async function saveSettings() {
    const payload = {
      requireFansMedal: document.getElementById("requireFansMedal").checked,
      minFansLevel: Number(document.getElementById("minFansLevel").value || 0),
      requireGuard: document.getElementById("requireGuard").checked,
      minGuardLevel: Number(document.getElementById("minGuardLevel").value || 1),
      maxQueueSize: Number(document.getElementById("maxQueueSize").value || 200),
    };
    await fetch(apiUrl("/api/settings/update"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await fetchSettings();
  }

  function connectWs() {
    if (ws) ws.close();
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/queue?token=${encodeURIComponent(token)}&roomKey=${encodeURIComponent(roomKey)}`);
    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "queueUpdate") renderQueue(msg.queue);
    };
  }

  document.getElementById("refreshBtn").addEventListener("click", async () => {
    roomKey = roomKeyInput.value.trim() || "all";
    connectWs();
    await fetchQueue();
    await fetchSettings();
  });

  document.getElementById("passNextBtn").addEventListener("click", async () => {
    await fetch(apiUrl("/api/queue/pass"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ roomKey }),
    });
  });

  document.getElementById("removeUserBtn").addEventListener("click", async () => {
    const userKey = document.getElementById("removeUserKey").value.trim();
    if (!userKey) return;
    await fetch(apiUrl("/api/queue/remove"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ roomKey, userKey }),
    });
  });

  document.getElementById("saveSettingsBtn").addEventListener("click", saveSettings);

  roomKey = params.get("roomKey") || "all";
  roomKeyInput.value = roomKey;
  connectWs();
  fetchQueue();
  fetchSettings();
})();
