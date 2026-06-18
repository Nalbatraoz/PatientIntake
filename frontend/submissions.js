document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-panel-target]");
  if (!button) return;
  const card = button.closest(".submission");
  const panel = document.getElementById(button.dataset.panelTarget);
  if (!card || !panel) return;

  const shouldOpen = panel.hidden;
  card.querySelectorAll(".submission-panel").forEach(function (item) {
    item.hidden = true;
  });
  card.querySelectorAll("[data-panel-target]").forEach(function (item) {
    item.setAttribute("aria-expanded", "false");
    item.classList.remove("submission-tab-active");
  });

  panel.hidden = !shouldOpen;
  button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
  button.classList.toggle("submission-tab-active", shouldOpen);
});

(function () {
  const STORAGE_KEY = "submissions-language";
  const toggleButton = document.getElementById("language-toggle");
  if (!toggleButton) return;

  function getLanguage() {
    return localStorage.getItem(STORAGE_KEY) === "ar" ? "ar" : "en";
  }

  function translateStaticText(language) {
    document.querySelectorAll("[data-i18n-en][data-i18n-ar]").forEach(function (node) {
      const value = language === "ar" ? node.dataset.i18nAr : node.dataset.i18nEn;
      if (value) node.textContent = value;
    });
  }

  function applyDirection(language) {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    document.body.classList.toggle("is-arabic", language === "ar");
  }

  function updateToggle(language) {
    toggleButton.textContent = language === "ar" ? (toggleButton.dataset.i18nAr || "English") : (toggleButton.dataset.i18nEn || "العربية");
    toggleButton.setAttribute("aria-pressed", language === "ar" ? "true" : "false");
  }

  function applyLanguage(language) {
    applyDirection(language);
    translateStaticText(language);
    updateToggle(language);
    localStorage.setItem(STORAGE_KEY, language);
    document.dispatchEvent(new CustomEvent("submissions-language-change", { detail: { language: language } }));
  }

  toggleButton.addEventListener("click", function () {
    applyLanguage(getLanguage() === "ar" ? "en" : "ar");
  });

  applyLanguage(getLanguage());
})();

/* Nanovate Figma shell */
(function () {
  const currentScript = document.currentScript;
  const titles = {
    "/": "Patient Intake",
    "/iief": "IIEF Questionnaire",
    "/pedt": "PEDT Questionnaire",
    "/low-libido": "Low Libido Questionnaire",
    "/ehs": "EHS Questionnaire",
    "/submissions": "Submissions",
    "/clinical-agent-test": "Clinical Agent Test"
  };

  const navItems = [
    ["./", "Dashboard", "M4 5h16M4 12h16M4 19h16"],
    ["iief", "IIEF", "M7 4h10v16H7zM9 8h6M9 12h6M9 16h3"],
    ["low-libido", "Low Libido", "M12 21s7-4.35 7-11a4 4 0 0 0-7-2.65A4 4 0 0 0 5 10c0 6.65 7 11 7 11z"],
    ["pedt", "PEDT", "M12 3v18M5 8h14M7 16h10"],
    ["ehs", "EHS", "M4 18h16M7 18V9m5 9V5m5 13v-6"],
    ["submissions", "Submissions", "M6 4h12v16H6zM9 8h6M9 12h6M9 16h4"]
  ];

  function normalizedPath() {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    const last = path.split("/").pop();
    return last ? `/${last}` : "/";
  }

  function pageTitle(path) {
    if (titles[path]) return titles[path];
    const heading = document.querySelector("h1");
    return heading ? heading.textContent.trim().split("\n")[0] : "Nanovate";
  }

  function icon(pathData) {
    return `<svg class="nv-nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="${pathData}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char]));
  }

  const formNav = [
    { href: "iief", path: "/iief", key: "iief" },
    { href: "low-libido", path: "/low-libido", key: "low-libido", complaint: "low_libido" },
    { href: "pedt", path: "/pedt", key: "pedt", complaint: "premature_ejaculation" },
    { href: "ehs", path: "/ehs", key: "ehs", complaint: "erectile_dysfunction" }
  ];

  function submissionId() {
    return new URLSearchParams(window.location.search).get("submission_id") || "";
  }

  function navStateKey() {
    const id = submissionId();
    return id ? `nanovate-form-progress:${id}` : "";
  }

  function readNavState() {
    const key = navStateKey();
    if (!key) return { available: [], originalComplaints: "" };
    try {
      return JSON.parse(localStorage.getItem(key) || "{}") || { available: [], originalComplaints: "" };
    } catch {
      return { available: [], originalComplaints: "" };
    }
  }

  function writeNavState(state) {
    const key = navStateKey();
    if (key) localStorage.setItem(key, JSON.stringify(state));
  }

  function currentComplaints() {
    return (new URLSearchParams(window.location.search).get("complaints") || "")
      .split(",")
      .map(item => item.trim())
      .filter(Boolean);
  }

  function availableFormKeys(activePath) {
    const id = submissionId();
    if (!id) return new Set();

    const state = readNavState();
    const available = new Set(Array.isArray(state.available) ? state.available : []);
    const complaints = currentComplaints();
    if (complaints.length && !state.originalComplaints) {
      state.originalComplaints = complaints.join(",");
    }

    available.add("iief");
    const activeForm = formNav.find(item => item.path === activePath);
    if (activeForm) available.add(activeForm.key);

    state.available = Array.from(available);
    writeNavState(state);
    return available;
  }

  function navHref(href) {
    if (href === "./" || href === "submissions") return href;
    const params = new URLSearchParams(window.location.search);
    const target = formNav.find(item => item.href === href);
    const state = readNavState();
    const complaints = currentComplaints();
    if (target?.complaint && !complaints.includes(target.complaint) && state.originalComplaints) {
      params.set("complaints", state.originalComplaints);
    }
    const query = params.toString();
    return query ? `${href}?${query}` : href;
  }

  function visibleNavItems(activePath) {
    const available = availableFormKeys(activePath);
    return navItems.filter(([href]) => {
      if (href === "./") return true;
      if (href === "submissions") return activePath === "/submissions";
      const form = formNav.find(item => item.href === href);
      return form ? available.has(form.key) : true;
    });
  }

  function progressStepIndex(activePath) {
    if (activePath === "/submissions") return formNav.length + 1;
    const formIndex = formNav.findIndex(item => item.path === activePath);
    return formIndex >= 0 ? formIndex + 1 : 0;
  }

  function pageScrollRatio() {
    const doc = document.documentElement;
    const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
    if (!maxScroll) return 0;
    return Math.max(0, Math.min(1, window.scrollY / maxScroll));
  }

  function progressPercent(activePath) {
    if (activePath === "/submissions") return 100;
    const totalSteps = formNav.length + 1;
    const percent = ((progressStepIndex(activePath) + pageScrollRatio()) / totalSteps) * 100;
    return Math.max(8, Math.min(100, Math.round(percent)));
  }

  function updateSidebarProgress(activePath) {
    const progressEl = document.querySelector("[data-nv-progress]");
    if (progressEl) progressEl.style.width = `${progressPercent(activePath)}%`;
  }

  function buildSidebar(activePath) {
    const links = visibleNavItems(activePath).map(([href, label, pathData]) => {
      const linkPath = href === "./" ? "/" : `/${href}`;
      const activeClass = activePath === linkPath ? " is-active" : "";
      return `<a class="nv-nav-link${activeClass}" href="${navHref(href)}">${icon(pathData)}<span>${label}</span></a>`;
    }).join("");
    const sidebarCredit = activePath === "/submissions" ? "" : `
        <div class="nv-sidebar-credit">
          <strong>Patient Intake</strong>
          <p>Complete your clinical intake before the visit.</p>
          <div class="nv-progress" aria-hidden="true"><span data-nv-progress></span></div>
        </div>
    `;

    return `
      <aside class="nv-sidebar" aria-label="Primary navigation">
        <div class="nv-brand">
          <span class="nv-brand-mark">N</span>
          <span class="nv-brand-name">Nanovate</span>
        </div>
        <nav class="nv-nav">${links}</nav>
        ${sidebarCredit}
      </aside>
    `;
  }

  function buildHeader(title) {
    return `
      <header class="nv-header">
        <div class="nv-breadcrumbs" aria-label="Breadcrumb">
          <span>Dashboard</span>
          <span>/</span>
          <span class="nv-page-title">${escapeHtml(title)}</span>
        </div>
        <div class="nv-header-actions">
          <div class="nv-search" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="m21 21-4.35-4.35M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            <span>Search</span>
          </div>
          <div class="nv-profile">
            <span class="nv-avatar" data-profile-avatar>P</span>
            <span class="nv-profile-details">
              <span class="nv-profile-name" data-profile-name>Profile</span>
              <span class="nv-profile-meta" data-profile-meta></span>
            </span>
          </div>
        </div>
      </header>
    `;
  }

  function fieldValue(name) {
    return document.querySelector(`[name="${name}"]`)?.value?.trim() || "";
  }

  function queryValue(name) {
    return new URLSearchParams(window.location.search).get(name)?.trim() || "";
  }

  function profileData() {
    const name = fieldValue("fullName") || fieldValue("name") || queryValue("name");
    const phone = fieldValue("mobile") || fieldValue("phone") || queryValue("phone");
    const age = fieldValue("age") || queryValue("age");
    const email = fieldValue("email") || queryValue("email");
    return { name, phone, age, email };
  }

  function updateProfile() {
    const data = profileData();
    const nameEl = document.querySelector("[data-profile-name]");
    const metaEl = document.querySelector("[data-profile-meta]");
    const avatarEl = document.querySelector("[data-profile-avatar]");
    if (!nameEl || !metaEl || !avatarEl) return;

    const name = data.name || "Profile";
    const meta = [
      data.phone && `Phone: ${data.phone}`,
      data.age && `Age: ${data.age}`,
      data.email
    ].filter(Boolean).join(" | ");

    nameEl.textContent = name;
    metaEl.textContent = meta;
    avatarEl.textContent = (data.name || "P").trim().charAt(0).toUpperCase() || "P";
  }

  function installPatientProfileSync() {
    ["fullName", "name", "mobile", "phone", "age", "email"].forEach(name => {
      document.querySelectorAll(`[name="${name}"]`).forEach(input => {
        input.addEventListener("input", updateProfile);
        input.addEventListener("change", updateProfile);
      });
    });

    document.addEventListener("nanovate-profile-update", updateProfile);
    document.addEventListener("click", event => {
      if (event.target.closest("#findPatientButton, #generateCodeButton, #submitButton")) {
        setTimeout(updateProfile, 0);
        setTimeout(updateProfile, 500);
      }
    });
    updateProfile();
  }

  function mountShell() {
    if (document.querySelector(".nv-shell")) return;

    const activePath = normalizedPath();
    const title = pageTitle(activePath);
    const shell = document.createElement("div");
    shell.className = "nv-shell";
    shell.innerHTML = `${buildSidebar(activePath)}<div class="nv-page">${buildHeader(title)}<main class="nv-content"></main></div>`;

    const content = shell.querySelector(".nv-content");
    const nodes = Array.from(document.body.childNodes).filter((node) => {
      if (node === currentScript) return false;
      if (node.nodeType === Node.TEXT_NODE && !node.textContent.trim()) return false;
      return true;
    });

    nodes.forEach((node) => content.appendChild(node));
    document.body.insertBefore(shell, currentScript || null);
    installPatientProfileSync();
    updateSidebarProgress(activePath);
    window.addEventListener("scroll", () => updateSidebarProgress(activePath), { passive: true });
    window.addEventListener("resize", () => updateSidebarProgress(activePath));
  }

  mountShell();
})();
