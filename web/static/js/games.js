(() => {
  const { request, webApp } = window.telegramApi;
  const chatSelect = document.getElementById("chat");
  const gamesElement = document.getElementById("games");
  const statusElement = document.getElementById("status");

  function renderGames(games) {
    gamesElement.replaceChildren();
    if (!games.length) {
      statusElement.textContent = "В этом чате нет активных игр.";
      return;
    }
    statusElement.textContent = "";
    for (const game of games) {
      const card = document.createElement("article");
      card.className = "game-card";
      const title = document.createElement("h2");
      title.textContent = game.description || "#игра";
      const details = document.createElement("p");
      details.textContent = `${new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium", timeStyle: "short",
      }).format(new Date(game.starts_at))} · ${game.duration_minutes} мин · ${game.price_per_hour} ₽/ч · до ${game.max_players_count} игроков`;
      card.append(title, details);
      if (game.message_url) {
        const openMessage = document.createElement("a");
        openMessage.className = "button-link";
        openMessage.href = game.message_url;
        openMessage.target = "_blank";
        openMessage.rel = "noopener";
        openMessage.textContent = "Открыть в чате";
        card.append(openMessage);
      } else {
        const unavailable = document.createElement("span");
        unavailable.className = "chat-link-unavailable";
        unavailable.textContent = "Прямая ссылка на сообщение для этого чата недоступна в Telegram.";
        card.append(unavailable);
      }
      if (game.can_edit) {
        const edit = document.createElement("a");
        edit.className = "button-link";
        edit.href = `/games/${game.id}/edit`;
        edit.textContent = "Редактировать";
        card.append(edit);

        const remove = document.createElement("button");
        remove.className = "danger-button";
        remove.type = "button";
        remove.textContent = "Удалить";
        remove.addEventListener("click", async () => {
          const confirmed = webApp?.showConfirm
            ? await new Promise((resolve) => webApp.showConfirm("Удалить игру и сообщение из чата?", resolve))
            : window.confirm("Удалить игру и сообщение из чата?");
          if (!confirmed) return;
          remove.disabled = true;
          statusElement.textContent = "Удаляем игру…";
          try {
            await request(`/api/telegram/games/${game.id}`, { method: "DELETE" });
            await loadGames();
          } catch (error) {
            statusElement.textContent = error.message;
            remove.disabled = false;
          }
        });
        card.append(remove);
      }
      gamesElement.append(card);
    }
  }

  async function loadGames() {
    if (!chatSelect.value) return;
    statusElement.textContent = "Загружаем игры…";
    try {
      const data = await request(`/api/telegram/games?chat_id=${encodeURIComponent(chatSelect.value)}`);
      renderGames(data.games);
    } catch (error) {
      gamesElement.replaceChildren();
      statusElement.textContent = error.message;
    }
  }

  async function init() {
    try {
      const data = await request("/api/telegram/chats");
      chatSelect.replaceChildren();
      for (const chat of data.chats) chatSelect.add(new Option(chat.title, chat.id));
      if (!data.chats.length) {
        statusElement.textContent = "Нет доступных чатов. Сначала взаимодействуйте с ботом в группе.";
        return;
      }
      chatSelect.addEventListener("change", loadGames);
      await loadGames();
    } catch (error) {
      statusElement.textContent = error.message;
    }
  }

  init();
})();
