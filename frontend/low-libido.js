// Low Libido Assessment Questionnaire - Browser Script
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get('submission_id');
    const fullName = urlParams.get('name') || urlParams.get('fullName');
    const age = urlParams.get('age');
    const phone = urlParams.get('phone') || urlParams.get('mobile');
    const email = urlParams.get('email');
    const codeNo = urlParams.get('codeNo') || (submissionId ? `INT-${submissionId}` : "");
    const complaints = (urlParams.get('complaints') || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    if (codeNo && !urlParams.get('codeNo')) {
        urlParams.set('codeNo', codeNo);
    }

    function buildForwardQuery(updatedComplaints) {
        const nextParams = new URLSearchParams(urlParams);
        nextParams.set('complaints', updatedComplaints.join(','));
        return nextParams.toString() ? `?${nextParams.toString()}` : '';
    }

    function resolveNextPage(updatedComplaints) {
        if (updatedComplaints.includes('premature_ejaculation')) return 'pedt';
        if (updatedComplaints.includes('erectile_dysfunction')) return 'ehs';
        return './';
    }

    if (!complaints.includes('low_libido')) {
        const nextPage = resolveNextPage(complaints);
        if (nextPage !== window.location.pathname) {
            window.location.replace(`${nextPage}${nextPage === './' ? '' : buildForwardQuery(complaints)}`);
        }
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

    const options = [
        [
            { val: 4, en: "Daily or more", ar: "يومياً أو أكثر" },
            { val: 3, en: "Several times a week", ar: "عدة مرات أسبوعياً" },
            { val: 2, en: "About once a week", ar: "مرة أسبوعياً" },
            { val: 1, en: "Less than once a week", ar: "أقل من مرة أسبوعياً" },
            { val: 0, en: "Almost none", ar: "لا توجد تقريباً" }
        ],
        [
            { val: 4, en: "Daily", ar: "يومياً" },
            { val: 3, en: "Several times a week", ar: "عدة مرات أسبوعياً" },
            { val: 2, en: "About once a week", ar: "مرة أسبوعياً" },
            { val: 1, en: "Rarely", ar: "نادراً" },
            { val: 0, en: "Never", ar: "أبداً" }
        ],
        [
            { val: 4, en: "Very high", ar: "مرتفع جداً" },
            { val: 3, en: "High", ar: "مرتفع" },
            { val: 2, en: "Moderate", ar: "متوسط" },
            { val: 1, en: "Low", ar: "منخفض" },
            { val: 0, en: "None", ar: "معدوم" }
        ],
        [
            { val: 4, en: "Very likely", ar: "عالية جداً" },
            { val: 3, en: "Likely", ar: "عالية" },
            { val: 2, en: "Moderately likely", ar: "متوسطة" },
            { val: 1, en: "Unlikely", ar: "منخفضة" },
            { val: 0, en: "Very unlikely", ar: "معدومة" }
        ],
        [
            { val: 4, en: "No", ar: "لا" },
            { val: 3, en: "A little less", ar: "أقل قليلاً" },
            { val: 2, en: "Moderately less", ar: "أقل بشكل متوسط" },
            { val: 1, en: "Much less", ar: "أقل كثيراً" },
            { val: 0, en: "Almost complete loss", ar: "فقدان شبه كامل" }
        ],
        [
            { val: 4, en: "No distress", ar: "لا" },
            { val: 3, en: "Mild", ar: "بسيط" },
            { val: 2, en: "Moderate", ar: "متوسط" },
            { val: 1, en: "Severe", ar: "شديد" },
            { val: 0, en: "Very severe", ar: "شديد جداً" }
        ],
        [
            { val: 4, en: "No effect", ar: "لا تأثير" },
            { val: 3, en: "Slight effect", ar: "تأثير بسيط" },
            { val: 2, en: "Moderate effect", ar: "متوسط" },
            { val: 1, en: "Clear effect", ar: "واضح" },
            { val: 0, en: "Severe effect", ar: "شديد" }
        ],
        [
            { val: 4, en: "Often", ar: "غالباً" },
            { val: 3, en: "Sometimes", ar: "أحياناً" },
            { val: 2, en: "Rarely", ar: "نادراً" },
            { val: 1, en: "Very rarely", ar: "نادراً جداً" },
            { val: 0, en: "Never", ar: "أبداً" }
        ],
        [
            { val: 4, en: "Very much", ar: "جداً" },
            { val: 3, en: "Well", ar: "جيداً" },
            { val: 2, en: "Moderately", ar: "متوسط" },
            { val: 1, en: "Weakly", ar: "ضعيف" },
            { val: 0, en: "Not at all", ar: "لا" }
        ],
        [
            { val: 4, en: "Higher", ar: "أعلى" },
            { val: 3, en: "About the same", ar: "مثلهم" },
            { val: 2, en: "Slightly lower", ar: "أقل قليلاً" },
            { val: 1, en: "Much lower", ar: "أقل كثيراً" },
            { val: 0, en: "Very low", ar: "منخفضة جداً" }
        ]
    ];

    const questions = [
        {
            id: 1,
            textEn: "How often did you feel sexual desire?",
            textAr: "كم مرة شعرت برغبة جنسية؟"
        },
        {
            id: 2,
            textEn: "How often did you have sexual thoughts or fantasies?",
            textAr: "كم مرة راودتك أفكار أو خيالات جنسية؟"
        },
        {
            id: 3,
            textEn: "How interested were you in having sex?",
            textAr: "ما مدى اهتمامك بممارسة الجنس؟"
        },
        {
            id: 4,
            textEn: "If a suitable sexual opportunity arose, how likely would you be to participate?",
            textAr: "إذا أتيحت فرصة جنسية مناسبة، ما احتمالية رغبتك في المشاركة؟"
        },
        {
            id: 5,
            textEn: "Do you feel your sexual desire is lower than before?",
            textAr: "هل تشعر أن رغبتك الجنسية أقل مما كانت عليه سابقاً؟"
        },
        {
            id: 6,
            textEn: "Does this cause you distress or discomfort?",
            textAr: "هل يسبب لك ذلك ضيقاً أو انزعاجاً؟"
        },
        {
            id: 7,
            textEn: "Does it affect your marital relationship?",
            textAr: "هل يؤثر على علاقتك الزوجية؟"
        },
        {
            id: 8,
            textEn: "How often do you initiate sexual activity?",
            textAr: "هل تبادر بالعلاقة الجنسية؟"
        },
        {
            id: 9,
            textEn: "Do you enjoy sexual stimulation (pictures, fantasies, touch)?",
            textAr: "هل تستمتع بالمثيرات الجنسية (صور، خيال، لمس)؟"
        },
        {
            id: 10,
            textEn: "How do you rate your current sexual desire compared with men your age?",
            textAr: "كيف تقيم رغبتك الجنسية الحالية مقارنة برجال في مثل عمرك؟"
        }
    ];

    const container = document.getElementById("questions");
    const optionLabels = [
        "score-4",
        "score-3",
        "score-2",
        "score-1",
        "score-0"
    ];

    questions.forEach((q, index) => {
        const div = document.createElement("div");
        div.className = "question-row";
        div.id = `q-row-${q.id}`;
        if (index % 2 === 0) {
            div.classList.add("shaded");
        }

        const questionOptions = options[index];
        let optionsHtml = "";
        questionOptions.forEach((opt, optIndex) => {
            optionsHtml += `
            <label class="option-item">
                <input type="radio" name="q${q.id}" value="${opt.val}" required>
                <span class="option-number ${optionLabels[optIndex]}">${opt.val}</span>
                <span class="option-label-text">
                    <span class="opt-en">${opt.en}</span>
                    <span class="opt-ar" dir="rtl">${opt.ar}</span>
                </span>
            </label>`;
        });

        div.innerHTML = `
            <div class="column-left">
                <div class="scorer-box" id="scorer-q${q.id}"></div>
                <span class="q-number">Q${q.id}</span>
            </div>
            <div class="column-middle">
                <p class="question-en">${q.textEn}</p>
                <p class="question-ar" dir="rtl">${q.textAr}</p>
            </div>
            <div class="column-right">
                <div class="options-vertical">${optionsHtml}</div>
            </div>
        `;

        container.appendChild(div);
    });

    document.addEventListener("change", function(e) {
        if (e.target.name && e.target.name.startsWith("q")) {
            const qId = e.target.name.substring(1);
            const val = e.target.value;
            const scorerBox = document.getElementById(`scorer-q${qId}`);
            if (scorerBox) {
                scorerBox.textContent = val;
                scorerBox.classList.add("filled");
            }
            const row = document.getElementById(`q-row-${qId}`);
            if (row) {
                row.classList.remove("error-highlight");
            }
        }
    });

    let currentStep = 1;

    function showStep(stepNum) {
        document.querySelectorAll(".step-container").forEach(el => {
            el.classList.add("hidden");
        });
        const currentContainer = document.getElementById(`step-${stepNum}`);
        if (currentContainer) {
            currentContainer.classList.remove("hidden");
            currentContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        currentStep = stepNum;
    }

    function validateForm() {
        const unanswered = [];
        questions.forEach(q => {
            const checked = document.querySelector(`input[name="q${q.id}"]:checked`);
            if (!checked) {
                unanswered.push(q.id);
            }
        });
        return unanswered;
    }

    function highlightUnanswered(ids) {
        ids.forEach(id => {
            const row = document.getElementById(`q-row-${id}`);
            if (row) {
                row.classList.add("error-highlight");
            }
        });
        if (ids.length > 0) {
            const firstRow = document.getElementById(`q-row-${ids[0]}`);
            if (firstRow) {
                firstRow.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
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

    document.getElementById("startBtn").addEventListener("click", () => {
        showStep(2);
    });

    document.getElementById("backToStep1").addEventListener("click", () => {
        showStep(1);
    });

    document.getElementById("lowLibidoForm").addEventListener("submit", async function(e) {
        e.preventDefault();

        const unanswered = validateForm();
        if (unanswered.length > 0) {
            highlightUnanswered(unanswered);
            alert("Please answer all questions before submitting.\nيرجى الإجابة على جميع الأسئلة قبل الإرسال.");
            return;
        }

        const submitBtn = document.getElementById("lowLibidoSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting answers... / جارٍ الإرسال...";

        let total = 0;
        const answers = {};

        questions.forEach(q => {
            const checkedRadio = document.querySelector(`input[name="q${q.id}"]:checked`);
            if (checkedRadio) {
                const val = parseInt(checkedRadio.value, 10);
                answers[`q${q.id}`] = val;
                total += val;
            }
        });

        let severityEn = "";
        let severityAr = "";
        let severityClass = "";

        if (total >= 35) {
            severityEn = "Excellent libido";
            severityAr = "رغبة ممتازة";
            severityClass = "severity-excellent";
        } else if (total >= 28) {
            severityEn = "Mild decrease";
            severityAr = "انخفاض بسيط";
            severityClass = "severity-mild";
        } else if (total >= 20) {
            severityEn = "Moderate decrease";
            severityAr = "انخفاض متوسط";
            severityClass = "severity-moderate";
        } else {
            severityEn = "Severe decrease";
            severityAr = "انخفاض شديد";
            severityClass = "severity-severe";
        }

        const low_libido_data = {
            answers: answers,
            scores: {
                total: total
            },
            severity: {
                en: severityEn,
                ar: severityAr,
                cssClass: severityClass
            }
        };

        try {
            const response = await fetch("submit-low-libido", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: submissionId || 0,
                    low_libido_data: low_libido_data
                })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Submission failed.");

            document.getElementById("step-1").style.display = "none";
            document.getElementById("step-2").style.display = "none";

            const remainingComplaints = complaints.filter(item => item !== 'low_libido');
            const nextPage = resolveNextPage(remainingComplaints);
            if (remainingComplaints.length > 0) {
                window.location.replace(`${nextPage}${buildForwardQuery(remainingComplaints)}`);
                return;
            }

            showCompletionCard(
                "This is your code. Please remember it for future visits.",
                "./",
                "Finish / إنهاء"
            );
            return;
        } catch (error) {
            console.error("Low Libido Submit error:", error);
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
