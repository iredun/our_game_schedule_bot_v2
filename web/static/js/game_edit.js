(() => {
  const { request, webApp } = window.telegramApi;
  const gameId = document.body.dataset.gameId;
  const form = document.getElementById("game-form");
  const statusElement = document.getElementById("status");
  const submitButton = document.getElementById("submit");

  async function loadGame() {
    try {
      const game = await request(`/api/telegram/games/${gameId}`);
      const startsAt = new Date(game.starts_at);
      document.getElementById("starts").value = new Date(
        startsAt.getTime() - startsAt.getTimezoneOffset() * 60000,
      ).toISOString().slice(0, 16);
      document.getElementById("description").value = game.description;
      document.getElementById("duration").value = game.duration_minutes;
      document.getElementById("price").value = game.price_per_hour;
      document.getElementById("players").value = game.max_players_count;
      if (game.message_url) {
        const messageLink = document.getElementById("message-link");
        messageLink.href = game.message_url;
        messageLink.hidden = false;
      }
      form.hidden = false;
    } catch (error) {
      statusElement.textContent = error.message;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitButton.disabled = true;
    statusElement.textContent = "Сохраняем…";
    const payload = {
      starts_at: new Date(document.getElementById("starts").value).toISOString(),
      description: document.getElementById("description").value,
      duration_minutes: Number(document.getElementById("duration").value),
      price_per_hour: Number(document.getElementById("price").value),
      max_players_count: Number(document.getElementById("players").value),
    };
    try {
      await request(`/api/telegram/games/${gameId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      statusElement.textContent = "Игра обновлена.";
      webApp?.HapticFeedback?.notificationOccurred("success");
      setTimeout(() => { window.location.href = "/games"; }, 900);
    } catch (error) {
      statusElement.textContent = error.message;
      submitButton.disabled = false;
    }
  });

  loadGame();
})();
