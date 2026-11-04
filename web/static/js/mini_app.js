(() => {
  const telegram = window.Telegram?.WebApp;
  const statusElement = document.getElementById("status");
  const chatSelect = document.getElementById("chat");
  const submitButton = document.getElementById("submit");
  const authorization = {
    headers: {
      Authorization: `tma ${telegram?.initData || ""}`,
      "Content-Type": "application/json",
    },
  };

  telegram?.ready();
  telegram?.expand();

  const defaultDate = new Date(Date.now() + 86400000);
  defaultDate.setMinutes(0, 0, 0);
  document.getElementById("starts").value = new Date(
    defaultDate.getTime() - defaultDate.getTimezoneOffset() * 60000,
  ).toISOString().slice(0, 16);

  async function loadChats() {
    const response = await fetch("/api/telegram/chats", authorization);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось загрузить чаты");

    chatSelect.replaceChildren();
    if (!data.chats.length) {
      chatSelect.add(new Option("Нет доступных чатов — напишите боту в нужной группе", ""));
      return;
    }
    for (const chat of data.chats) chatSelect.add(new Option(chat.title, chat.id));
  }

  loadChats().catch((error) => { statusElement.textContent = error.message; });

  document.getElementById("game-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    statusElement.textContent = "Публикуем…";
    submitButton.disabled = true;

    const body = {
      chat_id: Number(chatSelect.value),
      starts_at: new Date(document.getElementById("starts").value).toISOString(),
      description: document.getElementById("description").value,
      duration_minutes: Number(document.getElementById("duration").value),
      price_per_hour: Number(document.getElementById("price").value),
      max_players_count: Number(document.getElementById("players").value),
    };

    try {
      const response = await fetch("/api/telegram/games", {
        ...authorization,
        method: "POST",
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось создать игру");
      statusElement.textContent = "Игра опубликована.";
      if (data.message_url) {
        const link = document.createElement("a");
        link.className = "message-link";
        link.href = data.message_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Открыть сообщение в чате";
        statusElement.append(document.createElement("br"), link);
      }
      const listLink = document.createElement("a");
      listLink.className = "message-link";
      listLink.href = "/games";
      listLink.textContent = "Перейти к списку игр";
      statusElement.append(document.createElement("br"), listLink);
      telegram?.HapticFeedback?.notificationOccurred("success");
    } catch (error) {
      statusElement.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });
})();
