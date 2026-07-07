const form = document.getElementById("agent-form");
    const result = document.getElementById("result");
    const rawJson = document.getElementById("raw-json");

    // Escapes dynamic values before inserting them into HTML.
    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    // Renders an array as list items, or shows fallback text when the array is empty.
    function listItems(items, fallback) {
      if (!items || !items.length) {
        return `<p class="muted">${escapeHtml(fallback)}</p>`;
      }
      return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    // Builds the readable result panel from the clinical-agent JSON response.
    function renderClinicalResult(payload) {
      const agent = payload.clinical_agent || {};
      const report = agent.report || {};
      const checks = payload.medication_checks || {};
      const rag = payload.rag || {};
      const sources = rag.sources || [];
      const flags = checks.label_flags || [];
      const openfda = checks.openfda || [];
      const notes = payload.notes || [];
      const flagHtml = flags.length
        ? flags.map((flag) => `
            <div class="flag">
              <strong>${escapeHtml(flag.drug || "Medication flag")}</strong><br>
              ${escapeHtml(flag.message || "")}
            </div>
          `).join("")
        : `<div class="ok">No label interaction text flags were found for the parsed medication list.</div>`;
      const labelHtml = openfda.length
        ? `<ul>${openfda.map((item) => `
            <li>
              <strong>${escapeHtml(item.query)}</strong>:
              ${item.found ? "openFDA label found" : escapeHtml(item.message || item.error || "No label found")}
            </li>
          `).join("")}</ul>`
        : `<p class="muted">No medication names were parsed.</p>`;
      const sourceHtml = sources.length
        ? `<ul>${sources.map((source) => `
            <li>${escapeHtml(source.citation)} <span class="muted">score ${escapeHtml(source.score)}</span></li>
          `).join("")}</ul>`
        : `<p class="muted">No RAG sources returned.</p>`;

      result.innerHTML = `
        <div class="section">
          <h2>CrewAI Clinical Agent Review</h2>
          <p>${escapeHtml(report.clinical_summary || payload.message || "Clinical agent response received.")}</p>
          <p class="muted">Engine: ${escapeHtml(agent.engine || "gemini")} | Model: ${escapeHtml(agent.model || "")} | Confidence: ${escapeHtml(report.confidence || "not stated")}</p>
          ${agent.error ? `<div class="flag">${escapeHtml(agent.error)}</div>` : ""}
        </div>
        <div class="section">
          <h3>Safety Flags</h3>
          ${flagHtml}
        </div>
        <div class="section">
          <h3>CrewAI Key Findings</h3>
          ${listItems(report.key_findings || [], "No key findings returned.")}
        </div>
        <div class="section">
          <h3>CrewAI Medication Safety</h3>
          ${listItems(report.medication_safety || [], "No medication-safety summary returned.")}
        </div>
        <div class="section">
          <h3>CrewAI Guideline Context</h3>
          ${listItems(report.guideline_context || [], "No guideline-context summary returned.")}
        </div>
        <div class="section">
          <h3>Red Flags</h3>
          ${listItems(report.red_flags || [], "No red flags returned.")}
        </div>
        <div class="section">
          <h3>Missing Information</h3>
          ${listItems(report.missing_information || [], "No missing-information list returned.")}
        </div>
        <div class="section">
          <h3>Recommended Follow-up Questions</h3>
          ${listItems(report.recommended_next_questions || [], "No follow-up questions returned.")}
        </div>
        <div class="section">
          <h3>Medications Checked</h3>
          ${listItems(checks.drug_candidates || [], "No medication names were parsed.")}
        </div>
        <div class="section">
          <h3>openFDA Labels</h3>
          ${labelHtml}
        </div>
        <div class="section">
          <h3>Guideline Sources</h3>
          ${sourceHtml}
        </div>
        <div class="section">
          <h3>Retrieved Context</h3>
          <div class="passage">${escapeHtml(rag.context || "No context returned.")}</div>
        </div>
        <div class="section">
          <h3>Notes</h3>
          ${listItems(notes, "No notes returned.")}
        </div>
      `;
    }

    // Sends the form values to the clinical-agent endpoint and renders the response.
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      result.innerHTML = '<div class="muted">Running...</div>';
      rawJson.textContent = "Running...";
      const body = {
        query: document.getElementById("query").value,
        current_medications: document.getElementById("current-medications").value,
        medical_history: document.getElementById("medical-history").value,
        top_k: Number(document.getElementById("top-k").value || 1)
      };
      try {
        const response = await fetch("clinical-agent", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        const payload = await response.json();
        rawJson.textContent = JSON.stringify(payload, null, 2);
        renderClinicalResult(payload);
      } catch (error) {
        result.innerHTML = `<div class="flag">${escapeHtml(error)}</div>`;
        rawJson.textContent = String(error);
      }
    });

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

    return `
      <aside class="nv-sidebar" aria-label="Primary navigation">
        <div class="nv-brand">
          <span class="nv-brand-mark">N</span>
          <span class="nv-brand-name">Nanovate</span>
        </div>
        <nav class="nv-nav">${links}</nav>
        <div class="nv-sidebar-credit">
          <strong>Patient Intake</strong>
          <p>Complete your clinical intake before the visit.</p>
          <div class="nv-progress" aria-hidden="true"><span data-nv-progress></span></div>
        </div>
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
