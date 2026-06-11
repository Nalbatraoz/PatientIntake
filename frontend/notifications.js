/* notifications.js — real-time SSE notifications for the doctor's submissions page */
(function () {
  "use strict";

  // ── State ─────────────────────────────────────────────────────────────────
  let unreadCount = 0;
  const originalTitle = document.title;
  let retryDelay = 2000;
  let es = null;

  // ── Helpers ───────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function visitLabel(type) {
    return { urology: "Urology / مسالك", consultation: "Consultation / استشارة", examination: "Examination / كشف" }[type] || (type || "—");
  }

  // ── Build UI ──────────────────────────────────────────────────────────────
  function buildUI() {
    const toolbar = document.querySelector(".toolbar");
    if (!toolbar) {
      console.warn("[notifications] .toolbar not found — bell cannot be injected");
      return false;
    }

    // Bell button
    const bell = document.createElement("button");
    bell.id = "notif-bell";
    bell.className = "notif-bell";
    bell.setAttribute("aria-label", "Notifications");
    bell.setAttribute("aria-haspopup", "true");
    bell.setAttribute("aria-expanded", "false");
    bell.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
      <span id="notif-badge" class="notif-badge" hidden>0</span>
    `;
    toolbar.appendChild(bell);

    // Dropdown panel
    const panel = document.createElement("div");
    panel.id = "notif-panel";
    panel.className = "notif-panel";
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Recent notifications");
    panel.innerHTML = `
      <div class="notif-panel-header">
        <span>Notifications</span>
        <button id="notif-clear" class="notif-clear-btn" type="button">Clear all</button>
      </div>
      <ul id="notif-list" class="notif-list">
        <li class="notif-empty">No new submissions yet.</li>
      </ul>
      <div id="notif-status" class="notif-conn-status notif-conn-connecting">Connecting…</div>
    `;
    document.body.appendChild(panel);

    // Toast container
    const toasts = document.createElement("div");
    toasts.id = "notif-toasts";
    toasts.className = "notif-toasts";
    toasts.setAttribute("aria-live", "assertive");
    document.body.appendChild(toasts);

    // Bell toggle
    bell.addEventListener("click", function (e) {
      e.stopPropagation();
      const open = !panel.hidden;
      panel.hidden = open;
      bell.setAttribute("aria-expanded", String(!open));
      if (!open) clearUnread();
    });

    document.addEventListener("click", function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target !== bell) {
        panel.hidden = true;
        bell.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) {
        panel.hidden = true;
        bell.setAttribute("aria-expanded", "false");
        bell.focus();
      }
    });

    document.getElementById("notif-clear").addEventListener("click", function () {
      clearNotifList();
      clearUnread();
    });

    return true;
  }

  // ── Badge / title ─────────────────────────────────────────────────────────
  function incrementUnread() {
    unreadCount++;
    const badge = document.getElementById("notif-badge");
    if (badge) { badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount); badge.hidden = false; }
    document.title = "(" + unreadCount + ") " + originalTitle;
  }

  function clearUnread() {
    unreadCount = 0;
    const badge = document.getElementById("notif-badge");
    if (badge) badge.hidden = true;
    document.title = originalTitle;
  }

  // ── Panel list ────────────────────────────────────────────────────────────
  function clearNotifList() {
    const list = document.getElementById("notif-list");
    if (list) list.innerHTML = '<li class="notif-empty">No new submissions yet.</li>';
  }

  function prependToList(sub) {
    const list = document.getElementById("notif-list");
    if (!list) return;
    const empty = list.querySelector(".notif-empty");
    if (empty) empty.remove();

    const li = document.createElement("li");
    li.className = "notif-item";
    li.innerHTML = `
      <a href="#submission-${escHtml(String(sub.submission_id))}" class="notif-link">
        <span class="notif-name">${escHtml(sub.full_name)}</span>
        <span class="notif-meta">${escHtml(visitLabel(sub.visit_type))}${sub.age ? " · Age " + escHtml(String(sub.age)) : ""} · #${escHtml(String(sub.submission_id))}</span>
      </a>
      <time class="notif-time">${escHtml(sub.timestamp)}</time>
    `;
    li.querySelector(".notif-link").addEventListener("click", function () {
      const p = document.getElementById("notif-panel");
      if (p) p.hidden = true;
      const bell = document.getElementById("notif-bell");
      if (bell) bell.setAttribute("aria-expanded", "false");
    });
    list.prepend(li);

    // Cap list at 50
    const items = list.querySelectorAll(".notif-item");
    if (items.length > 50) items[items.length - 1].remove();
  }

  // ── Toast ─────────────────────────────────────────────────────────────────
  function showToast(sub) {
    const container = document.getElementById("notif-toasts");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "notif-toast";
    toast.setAttribute("role", "status");
    toast.innerHTML = `
      <div class="notif-toast-icon" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </div>
      <div class="notif-toast-body">
        <strong class="notif-toast-title">New patient submission</strong>
        <span class="notif-toast-sub">${escHtml(sub.full_name)}${sub.age ? " · Age " + escHtml(String(sub.age)) : ""} · ${escHtml(visitLabel(sub.visit_type))}</span>
      </div>
      <a href="#submission-${escHtml(String(sub.submission_id))}" class="notif-toast-action">View</a>
      <button class="notif-toast-close" aria-label="Dismiss" type="button">×</button>
    `;

    toast.querySelector(".notif-toast-close").addEventListener("click", function () { dismissToast(toast); });
    toast.querySelector(".notif-toast-action").addEventListener("click", function () { dismissToast(toast); });
    container.appendChild(toast);

    // Trigger enter animation
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { toast.classList.add("notif-toast-visible"); });
    });

    const timer = setTimeout(function () { dismissToast(toast); }, 7000);
    toast._dismissTimer = timer;
  }

  function dismissToast(toast) {
    clearTimeout(toast._dismissTimer);
    toast.classList.remove("notif-toast-visible");
    setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 400);
  }

  // ── Highlight new card ────────────────────────────────────────────────────
  function highlightNewSubmission(id) {
    const card = document.getElementById("submission-" + id);
    if (card) {
      card.classList.add("submission-new");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      setTimeout(function () { card.classList.remove("submission-new"); }, 6000);
    } else {
      // Card not in DOM yet (page may not have reloaded) — scroll to top
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  // ── Connection status ─────────────────────────────────────────────────────
  function setConnStatus(state) {
    const el = document.getElementById("notif-status");
    if (!el) return;
    el.className = "notif-conn-status notif-conn-" + state;
    el.textContent = { connecting: "Connecting…", live: "receiving updates", reconnecting: "Reconnecting…", error: "Connection lost — retrying" }[state] || state;
  }

  // ── SSE ───────────────────────────────────────────────────────────────────
  function connect() {
    if (es) { es.close(); es = null; }

    if (!window.EventSource) {
      console.warn("[notifications] EventSource not supported in this browser.");
      setConnStatus("error");
      return;
    }

    console.log("[notifications] Connecting to /events …");
    setConnStatus("connecting");
    es = new EventSource("/events");

    es.addEventListener("connected", function () {
      console.log("[notifications] SSE connected ✓");
      retryDelay = 2000;
      setConnStatus("live");
    });

    es.addEventListener("new_submission", function (event) {
      console.log("[notifications] new_submission received:", event.data);
      let sub;
      try { sub = JSON.parse(event.data); } catch (err) { console.error("[notifications] JSON parse error:", err); return; }
      incrementUnread();
      prependToList(sub);
      showToast(sub);
      highlightNewSubmission(sub.submission_id);
    });

    es.addEventListener("error", function (err) {
      console.warn("[notifications] SSE error, will retry in", retryDelay, "ms", err);
      es.close(); es = null;
      setConnStatus("reconnecting");
      setTimeout(function () { connect(); }, retryDelay);
      retryDelay = Math.min(retryDelay * 1.5, 30000);
    });
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  function init() {
    const uiReady = buildUI();
    if (uiReady) connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();