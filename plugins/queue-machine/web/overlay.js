(function () {
  const queueList = document.getElementById("queueList");
  const bannerWindow = document.getElementById("bannerWindow");
  const bannerInner = document.getElementById("bannerInner");
  let lastCallingId = null;
  let lastBannerText = null;
  let lastBannerFontSize = null;
  let autoScrollTimer = null;
  let autoScrollPauseUntil = 0;

  function fmtSeconds(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}h${m}m${s}s`;
    if (m > 0) return `${m}m${s}s`;
    return `${s}s`;
  }

  function render(snapshot) {
    const cfg = snapshot.config || {};
    applyTheme(cfg);
    updateBanner(cfg.banner_text, cfg.banner_font_size, false);
    const users = snapshot.users || [];
    const calling = snapshot.callingUserId || null;
    queueList.innerHTML = "";
    let callingNode = null;
    users.forEach((u) => {
      const item = document.createElement("div");
      item.className = "item";
      if (u.uid === calling && u.status !== "passed") {
        item.classList.add("calling");
        callingNode = item;
      }

      const valueText = u.status === "passed" ? "过号" : `¥${(u.giftValueCoin / 1000).toFixed(1)}`;
      const valueCls = u.status === "passed" ? "value passed" : "value";
      const callingTag = u.uid === calling && u.status !== "passed" ? "叫号中" : "";
      const rankText = u.status === "passed" ? "-" : String(u.rank || "");

      item.innerHTML = `
        <div class="rank">${rankText}</div>
        <img class="avatar" src="${u.avatarUrl || ""}" />
        <div class="meta">
          <div class="name">${u.name || u.uid}</div>
          ${callingTag ? `<div class="sub">${callingTag}</div>` : ""}
        </div>
        <div></div>
        <div class="${valueCls}">${valueText}</div>
      `;
      queueList.appendChild(item);
    });

    if (callingNode && calling !== lastCallingId) {
      callingNode.scrollIntoView({ behavior: "smooth", block: "center" });
      autoScrollPauseUntil = Date.now() + 1800;
    }
    lastCallingId = calling;
    ensureAutoScroll();
  }

  function updateBanner(raw, fontSize, force) {
    const text = String(raw || "").trim();
    const fontSizeNum = clampInt(Number(fontSize ?? 15), 12, 64);
    if (!force && text === lastBannerText && fontSizeNum === lastBannerFontSize && bannerInner.dataset.mode) return;
    lastBannerText = text;
    lastBannerFontSize = fontSizeNum;
    bannerInner.classList.remove("is-static", "is-scroll");
    bannerInner.style.animationDuration = "";
    bannerInner.style.removeProperty("--banner-shift");
    bannerInner.replaceChildren();
    if (!text) {
      bannerWindow.classList.add("hidden");
      delete bannerInner.dataset.mode;
      return;
    }
    bannerWindow.classList.remove("hidden");
    const span = document.createElement("span");
    span.textContent = text;
    bannerInner.appendChild(span);
    requestAnimationFrame(() => {
      const winW = bannerWindow.clientWidth - 20;
      const textW = span.scrollWidth;
      if (textW <= winW) {
        bannerInner.classList.add("is-static");
        bannerInner.dataset.mode = "static";
        return;
      }
      const sep = document.createElement("span");
      sep.className = "banner-sep";
      sep.setAttribute("aria-hidden", "true");
      const span2 = document.createElement("span");
      span2.textContent = text;
      bannerInner.appendChild(sep);
      bannerInner.appendChild(span2);
      const cycleW = span.offsetWidth + sep.offsetWidth;
      bannerInner.style.setProperty("--banner-shift", `${cycleW}px`);
      const sec = Math.max(10, cycleW / 45);
      bannerInner.style.animationDuration = `${sec}s`;
      bannerInner.classList.add("is-scroll");
      bannerInner.dataset.mode = "scroll";
    });
  }

  function applyTheme(cfg) {
    const root = document.documentElement;
    const boardColor = normalizeHex(cfg.board_color, "#000000");
    const itemColor = normalizeHex(cfg.item_color, "#000000");
    const boardOpacity = clamp01(Number(cfg.board_opacity ?? 0));
    const itemOpacity = clamp01(Number(cfg.item_opacity ?? 0.5));
    const boardRadius = clampInt(Number(cfg.board_radius ?? 0), 0, 80);
    const itemRadius = clampInt(Number(cfg.item_radius ?? 10), 0, 80);
    const bannerFontSize = clampInt(Number(cfg.banner_font_size ?? 15), 12, 64);
    root.style.setProperty("--board-bg", toRgba(boardColor, boardOpacity));
    root.style.setProperty("--item-bg", toRgba(itemColor, itemOpacity));
    root.style.setProperty("--board-radius", `${boardRadius}px`);
    root.style.setProperty("--item-radius", `${itemRadius}px`);
    root.style.setProperty("--banner-font-size", `${bannerFontSize}px`);
  }

  function clamp01(n) {
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(1, n));
  }

  function normalizeHex(v, fallback) {
    const s = String(v || "").trim();
    if (/^#[0-9a-fA-F]{6}$/.test(s)) return s;
    return fallback;
  }

  function toRgba(hex, alpha) {
    const m = /^#([0-9a-fA-F]{6})$/.exec(hex);
    if (!m) return `rgba(0,0,0,${alpha})`;
    const h = m[1];
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function clampInt(n, min, max) {
    if (!Number.isFinite(n)) return min;
    const i = Math.round(n);
    return Math.max(min, Math.min(max, i));
  }

  function ensureAutoScroll() {
    if (autoScrollTimer) return;
    autoScrollTimer = setInterval(() => {
      if (!queueList) return;
      const now = Date.now();
      if (now < autoScrollPauseUntil) return;
      const maxScroll = queueList.scrollHeight - queueList.clientHeight;
      if (maxScroll <= 4) {
        queueList.scrollTop = 0;
        return;
      }
      const next = queueList.scrollTop + 1;
      if (next >= maxScroll) {
        queueList.scrollTop = maxScroll;
        autoScrollPauseUntil = now + 1200;
        setTimeout(() => {
          queueList.scrollTop = 0;
          autoScrollPauseUntil = Date.now() + 1000;
        }, 1200);
      } else {
        queueList.scrollTop = next;
      }
    }, 35);
  }

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

  window.addEventListener("resize", () => {
    updateBanner(lastBannerText || "", lastBannerFontSize ?? 15, true);
  });

  loadSnapshot();
  connectWs();
})();
