(function () {
  const statusEl = document.getElementById("status");
  const bodyEl = document.getElementById("tableBody");
  const obsUrlEl = document.getElementById("obsUrl");
  const copyObsUrlBtn = document.getElementById("copyObsUrl");
  const minMedalInput = document.getElementById("minMedal");
  const saveMinMedalBtn = document.getElementById("saveMinMedal");
  const captainPriorityEnabledInput = document.getElementById("captainPriorityEnabled");
  const randomCountInput = document.getElementById("randomCount");
  const addRandomUsersBtn = document.getElementById("addRandomUsers");
  const clearQueueBtn = document.getElementById("clearQueue");
  const boardColorInput = document.getElementById("boardColor");
  const boardOpacityInput = document.getElementById("boardOpacity");
  const boardRadiusInput = document.getElementById("boardRadius");
  const itemColorInput = document.getElementById("itemColor");
  const itemOpacityInput = document.getElementById("itemOpacity");
  const itemRadiusInput = document.getElementById("itemRadius");
  const saveThemeBtn = document.getElementById("saveTheme");
  const bannerTextInput = document.getElementById("bannerText");
  const bannerFontSizeInput = document.getElementById("bannerFontSize");
  const saveBannerBtn = document.getElementById("saveBanner");
  let snapshot = null;

  function fmtTs(ts) {
    if (!ts) return "-";
    return new Date(ts * 1000).toLocaleString();
  }

  function coinToYuan(coin) {
    const n = Number(coin);
    if (!Number.isFinite(n) || n <= 0) return "0.0";
    return (n / 1000).toFixed(1);
  }

  function yuanToCoin(yuan) {
    const n = Number(yuan);
    if (!Number.isFinite(n) || n <= 0) return 0;
    return Math.round(n * 1000);
  }

  async function action(action, payload) {
    const res = await fetch("/api/admin/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, payload: payload || {} }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "操作失败");
      return;
    }
    if (data.snapshot) render(data.snapshot);
  }

  function render(s) {
    snapshot = s;
    const users = s.users || [];
    const cfg = s.config || {};
    if (Object.prototype.hasOwnProperty.call(cfg, "min_medal_level")) minMedalInput.value = cfg.min_medal_level;
    if (Object.prototype.hasOwnProperty.call(cfg, "board_color")) boardColorInput.value = cfg.board_color || "#000000";
    if (Object.prototype.hasOwnProperty.call(cfg, "board_opacity")) boardOpacityInput.value = cfg.board_opacity;
    if (Object.prototype.hasOwnProperty.call(cfg, "board_radius")) boardRadiusInput.value = cfg.board_radius;
    if (Object.prototype.hasOwnProperty.call(cfg, "item_color")) itemColorInput.value = cfg.item_color || "#000000";
    if (Object.prototype.hasOwnProperty.call(cfg, "item_opacity")) itemOpacityInput.value = cfg.item_opacity;
    if (Object.prototype.hasOwnProperty.call(cfg, "item_radius")) itemRadiusInput.value = cfg.item_radius;
    if (Object.prototype.hasOwnProperty.call(cfg, "banner_text")) bannerTextInput.value = cfg.banner_text || "";
    if (Object.prototype.hasOwnProperty.call(cfg, "banner_font_size")) bannerFontSizeInput.value = cfg.banner_font_size;
    if (Object.prototype.hasOwnProperty.call(cfg, "captain_priority_enabled")) {
      captainPriorityEnabledInput.checked = !!cfg.captain_priority_enabled;
    }
    statusEl.textContent = `当前人数: ${users.length}，当前叫号: ${s.callingUserId || "无"}`;
    bodyEl.innerHTML = "";
    users.forEach((u) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.rank}</td>
        <td>${u.name || u.uid}</td>
        <td>${u.medalLevel}</td>
        <td>${u.isCaptain ? "是" : "否"}</td>
        <td>
          <input data-type="gift" data-uid="${u.uid}" type="number" min="0" step="0.1" value="${coinToYuan(u.giftValueCoin)}" />
          <button data-type="gift-save" data-uid="${u.uid}">保存</button>
        </td>
        <td>${u.status === "passed" ? "过号" : "普通"}</td>
        <td>${fmtTs(u.queuedAt)}</td>
        <td class="ops">
          <button data-type="call" data-uid="${u.uid}">叫号</button>
          <button data-type="pass" data-uid="${u.uid}">过号</button>
          <button data-type="unpass" data-uid="${u.uid}">取消过号</button>
          <button data-type="remove" data-uid="${u.uid}">移除</button>
        </td>
      `;
      bodyEl.appendChild(tr);
    });
  }

  bodyEl.addEventListener("click", async (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLElement)) return;
    const type = target.getAttribute("data-type");
    const uid = target.getAttribute("data-uid") || "";
    if (!type) return;
    if (type === "call") return action("call_user", { uid });
    if (type === "pass") return action("mark_passed", { uid });
    if (type === "unpass") return action("unmark_passed", { uid });
    if (type === "remove") return action("remove_user", { uid });
    if (type === "gift-save") {
      const input = bodyEl.querySelector(`input[data-type="gift"][data-uid="${uid}"]`);
      const value = input ? Number(input.value) : 0;
      return action("set_gift_value", { uid, giftValueCoin: yuanToCoin(value) });
    }
  });

  saveMinMedalBtn.addEventListener("click", () => {
    action("set_min_medal_level", { value: Number(minMedalInput.value || 0) });
  });
  captainPriorityEnabledInput.addEventListener("change", () => {
    action("set_captain_priority_enabled", { value: captainPriorityEnabledInput.checked });
  });
  addRandomUsersBtn.addEventListener("click", () => {
    const count = Number(randomCountInput.value || 1);
    action("add_random_users", { count });
  });
  saveThemeBtn.addEventListener("click", () => {
    action("set_theme", {
      boardColor: boardColorInput.value,
      boardOpacity: Number(boardOpacityInput.value || 0),
      boardRadius: Number(boardRadiusInput.value || 0),
      itemColor: itemColorInput.value,
      itemOpacity: Number(itemOpacityInput.value || 0.5),
      itemRadius: Number(itemRadiusInput.value || 10),
    });
  });
  saveBannerBtn.addEventListener("click", () => {
    action("set_banner", {
      text: bannerTextInput.value || "",
      fontSize: Number(bannerFontSizeInput.value || 15),
    });
  });
  clearQueueBtn.addEventListener("click", () => {
    if (confirm("确认清空整个队列吗？")) action("clear_queue", {});
  });
  const overlayUrl = `${location.protocol}//${location.host}/overlay`;
  obsUrlEl.textContent = overlayUrl;
  copyObsUrlBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(overlayUrl);
      alert("已复制展示页地址");
    } catch (_e) {
      alert("复制失败，请手动复制");
    }
  });

  async function loadSnapshot() {
    const res = await fetch("/api/snapshot");
    if (!res.ok) return;
    render(await res.json());
  }

  function connectWs() {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "snapshot") render(msg.data || {});
      } catch (_e) {}
    };
    ws.onclose = () => setTimeout(connectWs, 1500);
  }

  loadSnapshot();
  connectWs();
})();
