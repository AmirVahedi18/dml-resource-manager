// Runs in <head>, after both the Telegram Web App SDK and htmx have loaded, so this listener
// is guaranteed to be registered before htmx processes any hx-trigger in the body.
document.addEventListener("htmx:configRequest", (event) => {
  event.detail.headers["X-Telegram-Init-Data"] = window.Telegram.WebApp.initData || "";
});

window.Telegram.WebApp.ready();
window.Telegram.WebApp.expand();
