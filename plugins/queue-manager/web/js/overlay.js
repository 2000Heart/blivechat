(function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";
  const roomKey = params.get("roomKey") || "all";
  const currentUser = document.getElementById("currentUser");
  const queueList = document.getElementById("queueList");

  function render(queue) {
    if (!queue.items || queue.items.length === 0) {
      currentUser.textContent = "暂无";
      queueList.innerHTML = "";
      return;
    }
    const first = queue.items[0];
    currentUser.textContent = `${first.authorName} (${first.giftTotalValue})`;
    queueList.innerHTML = "";
    queue.items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `${item.rank}. ${item.authorName} - ${item.giftTotalValue}`;
      queueList.appendChild(li);
    });
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/queue?token=${encodeURIComponent(token)}&roomKey=${encodeURIComponent(roomKey)}`);
    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "queueUpdate") render(msg.queue);
    };
    ws.onclose = () => setTimeout(connect, 1500);
  }

  connect();
})();
