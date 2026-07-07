// Erection Hardness Scale - Browser Script
(function() {
    const scale = [
        { value: 0, text: "Penis does not enlarge" },
        { value: 1, text: "Penis is larger, but not hard" },
        { value: 2, text: "Penis is hard, but not hard enough for penetration" },
        { value: 3, text: "Penis is hard enough for penetration, but not completely hard" },
        { value: 4, text: "Penis is completely hard and fully rigid" }
    ];

    const urlParams = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get("submission_id");
    const fullName = urlParams.get("name") || urlParams.get("fullName");
    const age = urlParams.get("age");
    const phone = urlParams.get("phone") || urlParams.get("mobile");
    const email = urlParams.get("email");
    const codeNo = urlParams.get("codeNo") || (submissionId ? `INT-${submissionId}` : "");
    const complaints = (urlParams.get("complaints") || "")
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);

    if (codeNo && !urlParams.get("codeNo")) {
        urlParams.set("codeNo", codeNo);
    }

    if (!complaints.includes("erectile_dysfunction")) {
        window.location.replace("./");
        return;
    }

    const nameInput = document.querySelector('[name="name"]');
    const ageInput = document.querySelector('[name="age"]');
    const phoneInput = document.querySelector('[name="phone"]');
    const emailInput = document.querySelector('[name="email"]');

    if (fullName && nameInput) nameInput.value = fullName;
    if (age && ageInput) ageInput.value = age;
    if (phone && phoneInput) phoneInput.value = phone;
    if (email && emailInput) emailInput.value = email;

    function renderScaleTable(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = scale.map(item => `
            <div class="scale-row">
                <div class="scale-score">${item.value}</div>
                <div class="scale-description">${item.text}</div>
            </div>
        `).join("");
    }

    function renderOptions(containerId, inputName) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = scale.map(item => `
            <label class="score-option">
                <input type="radio" name="${inputName}" value="${item.value}" required>
                <span class="score-option-card">
                    <span class="score-option-value">${item.value}</span>
                    <span class="score-option-text">${item.text}</span>
                </span>
            </label>
        `).join("");
    }

    function showStep(stepNum) {
        document.querySelectorAll(".step-container").forEach(el => {
            el.classList.add("hidden");
        });
        const currentContainer = document.getElementById(`step-${stepNum}`);
        if (currentContainer) {
            currentContainer.classList.remove("hidden");
            currentContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    function getCheckedValue(name) {
        const selected = document.querySelector(`input[name="${name}"]:checked`);
        return selected ? parseInt(selected.value, 10) : null;
    }

    function validateSelections() {
        const sections = ["withoutIntervention", "withIntervention"];
        const missing = [];
        sections.forEach(name => {
            const selected = document.querySelector(`input[name="${name}"]:checked`);
            const container = document.getElementById(`${name}Options`);
            if (!selected) {
                missing.push(container);
                if (container) {
                    container.classList.add("error-state");
                }
            } else if (container) {
                container.classList.remove("error-state");
            }
        });
        return missing;
    }

    function copyCodeToClipboard(code, button) {
        if (!code) return;
        const originalText = button?.textContent || "Copy code";
        const restoreText = function () {
            if (button) {
                button.textContent = "Copied!";
                setTimeout(function () {
                    button.textContent = originalText;
                }, 1400);
            }
        };
        const fallback = function () {
            const temp = document.createElement("textarea");
            temp.value = code;
            temp.setAttribute("readonly", "readonly");
            temp.style.position = "absolute";
            temp.style.left = "-9999px";
            document.body.appendChild(temp);
            temp.select();
            document.execCommand("copy");
            temp.remove();
        };

        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(code).then(restoreText).catch(function () {
                fallback();
                restoreText();
            });
        } else {
            fallback();
            restoreText();
        }
    }

    function showCompletionCard(message, continueHref, continueText) {
        const resultsDiv = document.getElementById("results");
        if (!resultsDiv) return;
        const completionCode = document.getElementById("completionCode");
        const completionMessage = document.getElementById("completionMessage");
        const continueBtn = document.getElementById("continueBtn");
        const copyButton = document.getElementById("copyCodeButton");
        const finalCode = codeNo || `INT-${submissionId || ""}`;

        if (completionCode) completionCode.textContent = finalCode;
        if (completionMessage) completionMessage.textContent = message;
        if (continueBtn && continueHref) {
            continueBtn.href = continueHref;
            continueBtn.textContent = continueText;
        }
        if (copyButton) {
            copyButton.onclick = function () {
                copyCodeToClipboard(finalCode, copyButton);
            };
        }

        resultsDiv.classList.remove("hidden");
        resultsDiv.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    renderScaleTable("scaleTable");
    renderScaleTable("resultsScaleTable");
    renderOptions("withoutInterventionOptions", "withoutIntervention");
    renderOptions("withInterventionOptions", "withIntervention");

    document.getElementById("startBtn").addEventListener("click", function() {
        showStep(2);
    });

    document.getElementById("backToStep1").addEventListener("click", function() {
        showStep(1);
    });

    document.addEventListener("change", function(event) {
        if (event.target.name === "withoutIntervention") {
            document.getElementById("withoutInterventionOptions").classList.remove("error-state");
        }
        if (event.target.name === "withIntervention") {
            document.getElementById("withInterventionOptions").classList.remove("error-state");
        }
    });

    document.getElementById("ehsForm").addEventListener("submit", async function(event) {
        event.preventDefault();

        const missing = validateSelections();
        if (missing.length > 0) {
            missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
            alert("Please select both EHS scores before submitting.\nيرجى اختيار الدرجتين قبل الإرسال.");
            return;
        }

        const submitBtn = document.getElementById("ehsSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting answers... / جارٍ الإرسال...";

        const withoutIntervention = getCheckedValue("withoutIntervention");
        const withIntervention = getCheckedValue("withIntervention");
        const change = withIntervention - withoutIntervention;

        let severityEn = "Unchanged";
        let severityAr = "بدون تغير";
        let severityClass = "severity-unchanged";
        if (change > 0) {
            severityEn = "Improved with intervention";
            severityAr = "تحسن مع التدخل";
            severityClass = "severity-improved";
        } else if (change < 0) {
            severityEn = "Lower with intervention";
            severityAr = "أقل مع التدخل";
            severityClass = "severity-lower";
        }

        const ehs_data = {
            answers: {
                without_intervention: withoutIntervention,
                with_intervention: withIntervention
            },
            scores: {
                without_intervention: withoutIntervention,
                with_intervention: withIntervention
            },
            severity: {
                en: severityEn,
                ar: severityAr,
                cssClass: severityClass
            }
        };

        try {
            const response = await fetch("submit-ehs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: submissionId || 0,
                    ehs_data: ehs_data
                })
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Submission failed.");
            }

            document.getElementById("step-1").style.display = "none";
            document.getElementById("step-2").style.display = "none";
            showCompletionCard(
                "This is your code. Please remember it for future visits.",
                "./",
                "Finish / إنهاء"
            );
            return;

            document.getElementById("withoutScore").textContent = `${withoutIntervention} / 4`;
            document.getElementById("withScore").textContent = `${withIntervention} / 4`;
            const badge = document.getElementById("assessment");
            badge.textContent = `${severityEn} / ${severityAr}`;
            badge.className = `severity-badge ${severityClass}`;

            const continueBtn = document.getElementById("continueBtn");
            if (continueBtn) {
                continueBtn.href = "./";
                continueBtn.textContent = "Finish / إنهاء";
            }

            const results = document.getElementById("results");
            results.classList.remove("hidden");
            results.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (error) {
            console.error("EHS Submit error:", error);
            alert("Error submitting questionnaire: " + error.message + "\nPlease try again.");
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit Questionnaire / إرسال الاستبيان";
        }
    });
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
