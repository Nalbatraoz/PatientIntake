document.addEventListener("DOMContentLoaded", function () {
  const panel = document.querySelector("[data-report-chat-panel]");
  if (!panel || !window.ReportChatPanel) return;

  window.ReportChatPanel.loadHistory(panel);

  const textarea = panel.querySelector("textarea[name='question']");
  if (textarea) textarea.focus({ preventScroll: true });
});