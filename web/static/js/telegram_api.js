(() => {
  const telegram = window.Telegram?.WebApp;
  telegram?.ready();
  telegram?.expand();

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        Authorization: `tma ${telegram?.initData || ""}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось выполнить запрос");
    return data;
  }

  window.telegramApi = { request, webApp: telegram };
})();
