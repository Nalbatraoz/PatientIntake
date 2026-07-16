function syncSubmissionPanelState(card) {
  if (!card) return;
  const layout = card.querySelector("[data-submission-panels-layout]");
  const hasPrimaryOpen = Array.from(
    card.querySelectorAll(".submission-panel:not([data-report-chat-panel])")
  ).some(function (panel) {
    return !panel.hidden;
  });
  const chatPanel = card.querySelector("[data-report-chat-panel]");
  const hasChatOpen = Boolean(chatPanel && !chatPanel.hidden);

  if (layout) {
    layout.classList.toggle("has-primary-open", hasPrimaryOpen);
    layout.classList.toggle("has-report-chat-open", hasChatOpen);
  }
}

function ensureReportChatOpen(card) {
  if (!card) return null;
  const chatPanel = card.querySelector("[data-report-chat-panel]");
  if (!chatPanel) return null;
  const chatButton = card.querySelector(`[data-panel-target="${chatPanel.id}"]`);
  const shouldLoad = chatPanel.hidden;
  chatPanel.hidden = false;
  if (chatButton) {
    chatButton.setAttribute("aria-expanded", "true");
    chatButton.classList.add("submission-tab-active");
  }
  if (shouldLoad && window.ReportChatPanel) {
    window.ReportChatPanel.loadHistory(chatPanel);
  }
  syncSubmissionPanelState(card);
  return chatPanel;
}

document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-panel-target]");
  if (!button) return;
  const card = button.closest(".submission");
  const panel = document.getElementById(button.dataset.panelTarget);
  if (!card || !panel) return;

  const shouldOpen = panel.hidden;
  const isChatPanel = panel.matches("[data-report-chat-panel]");

  if (isChatPanel) {
    panel.hidden = !shouldOpen;
    button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    button.classList.toggle("submission-tab-active", shouldOpen);
  } else {
    card.querySelectorAll(".submission-panel:not([data-report-chat-panel])").forEach(function (item) {
      item.hidden = true;
    });
    card.querySelectorAll("[data-panel-target]").forEach(function (item) {
      const targetPanel = document.getElementById(item.dataset.panelTarget);
      if (targetPanel && targetPanel.matches("[data-report-chat-panel]")) {
        return;
      }
      item.setAttribute("aria-expanded", "false");
      item.classList.remove("submission-tab-active");
    });

    panel.hidden = !shouldOpen;
    button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    button.classList.toggle("submission-tab-active", shouldOpen);
    if (shouldOpen) ensureReportChatOpen(card);
  }

  if (shouldOpen && panel.matches("[data-report-chat-panel]") && window.ReportChatPanel) {
    window.ReportChatPanel.loadHistory(panel);
  }
  syncSubmissionPanelState(card);
});

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".submission").forEach(syncSubmissionPanelState);
});

(function () {
  const loadedPanels = new WeakSet();
  const loadingPanels = new WeakSet();

  function chatEscapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char];
    });
  }

  function messagesElement(panel) {
    return panel.querySelector("[data-report-chat-messages]");
  }

  function statusElement(panel) {
    return panel.querySelector("[data-report-chat-status]");
  }

  function reportDocumentContent(panel) {
    return panel.closest(".report-chat-shell")?.querySelector(".report-document-scroll .ai-report-content") || null;
  }

  function reportPdfLink(panel) {
    return panel.closest(".report-chat-shell")?.querySelector(".report-pdf-link") || null;
  }

  function fillPanelElement(panel) {
    return panel.querySelector("[data-report-fill-panel]");
  }

  function fillToggleButton(panel) {
    return panel.querySelector("[data-report-fill-toggle]");
  }

  function fillApplyButton(panel) {
    return panel.querySelector("[data-report-apply-button]");
  }

  function missingInfoScript(panel) {
    return panel.querySelector("[data-report-missing-information]");
  }

  function readMissingInformation(panel) {
    const script = missingInfoScript(panel);
    if (!script) return [];
    try {
      const values = JSON.parse(script.textContent || "[]");
      return Array.isArray(values) ? values : [];
    } catch {
      return [];
    }
  }

  function writeMissingInformation(panel, values) {
    const script = missingInfoScript(panel);
    if (!script) return;
    script.textContent = JSON.stringify(Array.isArray(values) ? values : []);
  }

  function renderMissingInformationPanel(panel) {
    const list = panel.querySelector("[data-report-missing-list]");
    if (!list) return;
    const items = readMissingInformation(panel);
    if (!items.length) {
      list.innerHTML = "<li>All currently listed missing-information items have been addressed in the saved report.</li>";
      return;
    }
    list.innerHTML = items.map(function (item, index) {
      return `<li class="report-missing-field" data-missing-item="${chatEscapeHtml(item)}">
        <label for="missing-field-${index}">${chatEscapeHtml(item)}</label>
        <textarea id="missing-field-${index}" rows="2" maxlength="2000" placeholder="Enter this missing information"></textarea>
        <button type="button" class="report-apply-button" data-report-apply-button data-idle-label="Apply this field" data-loading-label="Updating...">Apply this field</button>
      </li>`;
    }).join("");
  }

  function setFillMode(panel, isActive) {
    if (!panel) return;
    const fillPanel = fillPanelElement(panel);
    const prompts = panel.querySelector(".report-chat-prompts");
    const questionForm = panel.querySelector("[data-report-chat-form]");
    const toggle = fillToggleButton(panel);
    panel.dataset.reportFillMode = isActive ? "true" : "false";
    if (fillPanel) {
      fillPanel.hidden = !isActive;
      if (isActive) renderMissingInformationPanel(panel);
    }
    if (prompts) prompts.hidden = isActive;
    if (questionForm) questionForm.hidden = isActive;
    if (toggle) toggle.classList.toggle("is-active", isActive);
  }

  function patchSummaryHtml(payload) {
    const before = Array.isArray(payload.missing_information_before) ? payload.missing_information_before.length : 0;
    const after = Array.isArray(payload.missing_information_after) ? payload.missing_information_after.length : 0;
    const resolved = Math.max(0, before - after);
    return `
      <p>${resolved ? `${resolved} missing-information item${resolved === 1 ? "" : "s"} addressed and the saved report was patched.` : "The saved report was patched with the doctor's supplied information."}</p>
      ${renderList("Remaining Missing Information", payload.missing_information_after || [])}
    `;
  }

  function syncPatchedReport(panel, payload) {
    const content = reportDocumentContent(panel);
    if (content && payload.ai_html) {
      content.innerHTML = payload.ai_html;
    }
    if (Array.isArray(payload.missing_information_after)) {
      writeMissingInformation(panel, payload.missing_information_after);
      renderMissingInformationPanel(panel);
    }
    const pdfLink = reportPdfLink(panel);
    if (pdfLink && payload.report_pdf_url) {
      pdfLink.href = payload.report_pdf_url;
      pdfLink.hidden = false;
    }
  }

  function setSubmitButtonState(button, isLoading) {
    if (!button) return;
    const idleLabel = button.dataset.idleLabel || "Ask";
    const loadingLabel = button.dataset.loadingLabel || "Generating...";
    button.disabled = Boolean(isLoading);
    const label = button.querySelector("span");
    if (label) {
      label.textContent = isLoading ? loadingLabel : idleLabel;
    } else {
      button.textContent = isLoading ? loadingLabel : idleLabel;
    }
    button.setAttribute("aria-busy", isLoading ? "true" : "false");
  }

  function setStatus(panel, message, isError) {
    const status = statusElement(panel);
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  async function readJsonResponse(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.error || "The report chat request failed.");
    }
    return payload;
  }

  function clearEmptyState(panel) {
    const empty = panel.querySelector("[data-report-chat-empty]");
    if (empty) empty.remove();
  }

  function emptyStateHtml() {
    return `
      <div class="report-chat-empty" data-report-chat-empty>
        <span class="report-chat-empty-mark" aria-hidden="true">N</span>
        <span>No questions yet.</span>
      </div>
    `;
  }

  function doctorAvatarHtml() {
    return `
      <span class="nv-niva-message-item__avatar report-chat-avatar report-chat-avatar-doctor">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/>
        </svg>
      </span>
    `;
  }

  function agentAvatarHtml() {
    return `
      <span class="nv-niva-message-item__avatar report-chat-avatar report-chat-avatar-agent" aria-hidden="true">
        <span>N</span>
      </span>
    `;
  }

  function isNearLatest(messages) {
    return messages.scrollHeight - messages.scrollTop - messages.clientHeight < 140;
  }

  function jumpButtonElement(panel) {
    return panel.querySelector("[data-report-chat-jump]");
  }

  function updateJumpButton(panel) {
    const messages = messagesElement(panel);
    const jumpButton = jumpButtonElement(panel);
    if (!messages || !jumpButton) return;
    jumpButton.hidden = isNearLatest(messages);
  }

  function scrollToLatest(panel, behavior) {
    const messages = messagesElement(panel);
    if (!messages) return;
    if (behavior === "auto") {
      const previous = messages.style.scrollBehavior;
      messages.style.scrollBehavior = "auto";
      messages.scrollTop = messages.scrollHeight;
      messages.style.scrollBehavior = previous;
    } else {
      messages.scrollTop = messages.scrollHeight;
    }
    updateJumpButton(panel);
  }

  function ensureChatScrollControls(panel) {
    const messages = messagesElement(panel);
    const bottom = panel.querySelector(".report-chat-bottom");
    if (!messages || !bottom || jumpButtonElement(panel)) return;

    bottom.insertAdjacentHTML("afterbegin", `
      <button type="button" class="report-chat-jump-latest" data-report-chat-jump hidden>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 5v14m0 0 6-6m-6 6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>Latest messages</span>
      </button>
    `);
    jumpButtonElement(panel)?.addEventListener("click", function () {
      scrollToLatest(panel);
    });
    messages.addEventListener("scroll", function () {
      updateJumpButton(panel);
    }, { passive: true });
  }

  function setTyping(panel, isTyping) {
    const messages = messagesElement(panel);
    if (!messages) return;
    const existing = messages.querySelector("[data-report-chat-typing]");
    if (!isTyping) {
      if (existing) existing.remove();
      return;
    }
    if (existing) return;
    clearEmptyState(panel);
    messages.insertAdjacentHTML("beforeend", `
      <div class="nv-niva-typing report-chat-typing" data-report-chat-typing aria-label="Nanovate is typing">
        <span></span><span></span><span></span>
      </div>
    `);
    messages.scrollTop = messages.scrollHeight;
  }

  function appendMessage(panel, role, html, meta) {
    const messages = messagesElement(panel);
    if (!messages) return;
    clearEmptyState(panel);
    const isDoctor = role === "doctor";
    // Keep the view pinned to the newest message only when the doctor just sent
    // one or was already reading the latest; otherwise offer the jump button so
    // scrolling back through the conversation is never interrupted.
    const shouldStick = isDoctor || isNearLatest(messages);
    const roleLabel = isDoctor ? "Doctor" : "Nanovate";
    const roleClass = isDoctor ? "doctor" : "agent";
    const metaHtml = meta ? `<span class="nv-niva-message-item__time">${chatEscapeHtml(meta)}</span>` : "";
    const nameHtml = `<span class="nv-niva-message-item__name">${roleLabel}</span>`;
    const metaRow = isDoctor ? `${metaHtml}${nameHtml}` : `${nameHtml}${metaHtml}`;
    const avatar = isDoctor ? doctorAvatarHtml() : agentAvatarHtml();
    const content = `
      <div class="nv-niva-message-item__content">
        <div class="nv-niva-message-item__meta">${metaRow}</div>
        <div class="report-chat-message-body nv-niva-message-item__bubble" dir="auto">${html}</div>
      </div>
    `;
    messages.insertAdjacentHTML("beforeend", `
      <article class="report-chat-message report-chat-message-${roleClass} nv-niva-message-item${isDoctor ? " nv-niva-message-item--user" : ""}" data-niva-role="${isDoctor ? "user" : "niva"}">
        ${isDoctor ? `${content}${avatar}` : `${avatar}${content}`}
      </article>
    `);
    if (shouldStick) {
      messages.scrollTop = messages.scrollHeight;
    }
    updateJumpButton(panel);
  }

  function appendDoctorMessage(panel, question, meta) {
    appendMessage(panel, "doctor", `<p>${chatEscapeHtml(question)}</p>`, meta);
  }

  function renderReferences(references) {
    if (!Array.isArray(references) || !references.length) return "";
    const items = references.map(function (item) {
      if (!item) return "";
      const evidenceSource = chatEscapeHtml(
        item.evidence_source || item.label || "Saved Clinical Record"
      );
      const recordLocation = chatEscapeHtml(
        item.record_location || item.source_type || "Saved clinical record"
      );
      const supportingEvidence = chatEscapeHtml(
        item.supporting_evidence || item.support || ""
      );
      return `
        <li>
          <strong>${evidenceSource}</strong>
          <span>${recordLocation}</span>
          ${supportingEvidence ? `<p>${supportingEvidence}</p>` : ""}
        </li>
      `;
    }).join("");
    return `<div class="report-chat-references"><h4>References</h4><ul>${items}</ul></div>`;
  }

  function renderList(title, values) {
    if (!Array.isArray(values) || !values.length) return "";
    const items = values.map(function (value) {
      return `<li>${chatEscapeHtml(value)}</li>`;
    }).join("");
    return `<div class="report-chat-detail"><h4>${title}</h4><ul>${items}</ul></div>`;
  }

  function normalizeReferences(answer) {
    const candidates = [
      answer && answer.references,
      answer && answer.evidence,
      answer && answer.citations,
      answer && answer.supporting_references,
      answer && answer.sources
    ];
    const list = candidates.find(Array.isArray) || [];
    return list.map(function (item) {
      if (!item) return null;
      if (typeof item === "string") {
        return {
          evidence_source: "Saved Clinical Record",
          record_location: "Saved clinical record",
          supporting_evidence: item
        };
      }
      if (typeof item === "object") {
        return {
          evidence_source: item.evidence_source || item.label || item.title || "Saved Clinical Record",
          record_location: item.record_location || item.section || item.source_type || item.type || item.kind || "Saved clinical record",
          supporting_evidence: item.supporting_evidence || item.support || item.text || item.quote || item.detail || ""
        };
      }
      return null;
    }).filter(Boolean);
  }

  function normalizeAnswer(answer, answerText) {
    if (typeof answer === "string") {
      return {
        direct: answer,
        reasoning: "",
        references: [],
        uncertainty: "",
        limitations: []
      };
    }

    const safeAnswer = answer && typeof answer === "object" ? answer : {};
    const direct = safeAnswer.direct_answer
      || safeAnswer.answer
      || safeAnswer.response
      || safeAnswer.text
      || answerText
      || "The saved clinical record does not contain enough information to answer that question.";

    const reasoning = safeAnswer.reasoning_summary
      || safeAnswer.reasoning
      || safeAnswer.explanation
      || safeAnswer.why
      || "";

    const uncertainty = safeAnswer.uncertainty
      || safeAnswer.unknowns
      || safeAnswer.missing_information
      || "";

    const limitations = Array.isArray(safeAnswer.limitations)
      ? safeAnswer.limitations
      : Array.isArray(safeAnswer.caveats)
        ? safeAnswer.caveats
        : [];

    return {
      direct: direct,
      reasoning: reasoning,
      references: normalizeReferences(safeAnswer),
      uncertainty: uncertainty,
      limitations: limitations
    };
  }

  function appendAgentMessage(panel, answer, meta, answerText) {
    const normalized = normalizeAnswer(answer, answerText);
    const html = `
      <p>${chatEscapeHtml(normalized.direct)}</p>
      ${normalized.reasoning ? `<div class="report-chat-detail"><h4>Reasoning</h4><p>${chatEscapeHtml(normalized.reasoning)}</p></div>` : ""}
      ${renderReferences(normalized.references)}
      ${normalized.uncertainty ? `<div class="report-chat-detail"><h4>Uncertainty</h4><p>${chatEscapeHtml(normalized.uncertainty)}</p></div>` : ""}
      ${renderList("Limitations", normalized.limitations)}
    `;
    appendMessage(panel, "agent", html, meta);
  }

  function renderHistory(panel, history) {
    const messages = messagesElement(panel);
    if (!messages) return;
    messages.innerHTML = "";
    if (!Array.isArray(history) || !history.length) {
      messages.innerHTML = emptyStateHtml();
      return;
    }
    history.forEach(function (item) {
      appendDoctorMessage(panel, item.question || "", item.created_at || "");
      appendAgentMessage(panel, item.answer || {}, item.created_at || "", item.answer_text || "");
    });
    scrollToLatest(panel, "auto");
  }

  async function loadHistory(panel) {
    if (!panel || loadedPanels.has(panel) || loadingPanels.has(panel)) return;
    ensureChatScrollControls(panel);
    loadingPanels.add(panel);
    setStatus(panel, "Loading report chat history...", false);
    try {
      const submissionId = panel.dataset.submissionId || panel.dataset.codeNo || "";
      const response = await fetch(`report-chat/history?submission_id=${encodeURIComponent(submissionId)}`, {
        credentials: "same-origin"
      });
      const payload = await readJsonResponse(response);
      renderHistory(panel, payload.history || []);
      loadedPanels.add(panel);
      setStatus(panel, "", false);
    } catch (error) {
      setStatus(panel, error.message || "Could not load report chat history.", true);
    } finally {
      loadingPanels.delete(panel);
    }
  }

  // Purpose: Enter sends the question (Shift+Enter keeps a new line).
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    const textarea = event.target.closest("[data-report-chat-form] textarea[name='question']");
    if (!textarea || textarea.disabled) return;
    event.preventDefault();
    const form = textarea.closest("form");
    if (!form) return;
    if (typeof form.requestSubmit === "function") form.requestSubmit();
    else form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });

  // Purpose: grow the question box with its content instead of forcing inner scroll.
  document.addEventListener("input", function (event) {
    const textarea = event.target.closest("[data-report-chat-form] textarea[name='question']");
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
  });

  document.addEventListener("click", function (event) {
    const promptButton = event.target.closest("[data-report-chat-prompt]");
    if (!promptButton) return;
    const panel = promptButton.closest("[data-report-chat-panel]");
    const textarea = panel ? panel.querySelector("textarea[name='question']") : null;
    if (!textarea) return;
    textarea.value = promptButton.dataset.reportChatPrompt || "";
    textarea.focus();
  });

  document.addEventListener("click", function (event) {
    const toggleButton = event.target.closest("[data-report-fill-toggle]");
    if (!toggleButton) return;
    const panel = toggleButton.closest("[data-report-chat-panel]");
    const textarea = panel ? panel.querySelector("textarea[name='question']") : null;
    if (!panel) return;
    setFillMode(panel, panel.dataset.reportFillMode !== "true");
    if (textarea) textarea.focus();
  });

  document.addEventListener("click", function (event) {
    const cancelButton = event.target.closest("[data-report-fill-cancel]");
    if (!cancelButton) return;
    const panel = cancelButton.closest("[data-report-chat-panel]");
    const textarea = panel ? panel.querySelector("textarea[name='question']") : null;
    if (!panel) return;
    setFillMode(panel, false);
    if (textarea) textarea.focus();
  });

  document.addEventListener("click", async function (event) {
    const applyButton = event.target.closest("[data-report-apply-button]");
    if (!applyButton) return;

    const panel = applyButton.closest("[data-report-chat-panel]");
    const row = applyButton.closest("[data-missing-item]");
    const textarea = row ? row.querySelector("textarea") : null;
    const toggleButton = panel ? fillToggleButton(panel) : null;
    const filledInformation = textarea ? textarea.value.trim() : "";
    const missingItem = row ? row.dataset.missingItem || "" : "";
    if (!panel || !textarea || !filledInformation) {
      if (panel) setStatus(panel, "Enter the missing information you want applied to this report.", true);
      return;
    }

    appendDoctorMessage(panel, filledInformation, "Now");
    textarea.value = "";
    textarea.disabled = true;
    setSubmitButtonState(applyButton, true);
    if (toggleButton) toggleButton.disabled = true;
    setStatus(panel, "Patching the saved report with the doctor's information...", false);

    try {
      const response = await fetch("report-chat/report-patch", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_id: panel.dataset.submissionId || panel.dataset.codeNo,
          missing_item: missingItem,
          filled_information: filledInformation
        })
      });
      const payload = await readJsonResponse(response);
      syncPatchedReport(panel, payload);
      appendMessage(panel, "agent", patchSummaryHtml(payload), payload.patch_entry?.created_at || "");
      setFillMode(panel, true);
      setStatus(panel, "One missing field was saved and the report was updated.", false);
    } catch (error) {
      setStatus(panel, error.message || "Could not patch the saved report.", true);
    } finally {
      textarea.disabled = false;
      setSubmitButtonState(applyButton, false);
      if (toggleButton) toggleButton.disabled = false;
      textarea.focus();
    }
  });

  document.addEventListener("submit", async function (event) {
    const form = event.target.closest("[data-report-chat-form]");
    if (!form) return;
    event.preventDefault();

    const panel = form.closest("[data-report-chat-panel]");
    const textarea = form.querySelector("textarea[name='question']");
    const submitButton = form.querySelector("button[type='submit']");
    if (panel?.dataset.reportFillMode === "true") {
      if (panel) setStatus(panel, "Use Apply to Report while Fill Missing Information is open.", true);
      return;
    }
    const question = textarea ? textarea.value.trim() : "";
    if (!panel || !textarea || !question) {
      if (panel) setStatus(panel, "Enter a question about this report.", true);
      return;
    }

    appendDoctorMessage(panel, question, "Now");
    textarea.value = "";
    textarea.disabled = true;
    setSubmitButtonState(submitButton, true);
    setStatus(panel, "Generating answer from this report...", false);
    setTyping(panel, true);

    try {
      const response = await fetch("report-chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_id: panel.dataset.submissionId || panel.dataset.codeNo,
          question: question
        })
      });
      const payload = await readJsonResponse(response);
      setTyping(panel, false);
      appendAgentMessage(panel, payload.answer || {}, payload.created_at || "");
      loadedPanels.add(panel);
      setStatus(panel, "", false);
    } catch (error) {
      setTyping(panel, false);
      setStatus(panel, error.message || "The report chat agent could not answer.", true);
    } finally {
      setTyping(panel, false);
      textarea.disabled = false;
      setSubmitButtonState(submitButton, false);
      textarea.focus();
    }
  });

  window.ReportChatPanel = {
    loadHistory: loadHistory,
    renderMissingInformationPanel: renderMissingInformationPanel
  };
})();

/* Search submissions by phone number (also matches name and patient code). */
(function () {
  const input = document.getElementById("submissionsSearch");
  if (!input) return;
  const clearButton = document.getElementById("submissionsSearchClear");
  const emptyMessage = document.getElementById("submissionsSearchEmpty");

  const EASTERN_DIGITS = { "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9", "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9" };

  function normalizeDigits(value) {
    return String(value || "").replace(/[٠-٩۰-۹]/g, char => EASTERN_DIGITS[char] || char);
  }

  function digitsOnly(value) {
    return normalizeDigits(value).replace(/\D+/g, "");
  }

  function applyFilter() {
    const query = normalizeDigits(input.value).trim().toLowerCase();
    const queryDigits = digitsOnly(query);
    let visibleCount = 0;

    document.querySelectorAll("article.submission").forEach(function (card) {
      const mobileDigits = digitsOnly(card.dataset.mobile || "");
      const name = (card.dataset.name || "").toLowerCase();
      const code = (card.dataset.code || "").toLowerCase();
      const matches = !query
        || (queryDigits && mobileDigits.includes(queryDigits))
        || name.includes(query)
        || code.includes(query);
      card.hidden = !matches;
      if (matches) visibleCount += 1;
    });

    if (emptyMessage) emptyMessage.hidden = visibleCount > 0 || !query;
    if (clearButton) clearButton.hidden = !query;
  }

  input.addEventListener("input", applyFilter);
  input.addEventListener("search", applyFilter);
  clearButton?.addEventListener("click", function () {
    input.value = "";
    applyFilter();
    input.focus();
  });
})();

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

(function () {
  const scalarFields = [
    ["report_title", "Report title"],
    ["report_type", "Report type"],
    ["confidence", "Confidence"],
    ["executive_summary", "Executive summary"],
    ["clinical_summary", "Clinical summary"]
  ];
  const listFields = [
    ["urgent_safety_alerts", "Urgent safety alerts"],
    ["medication_safety", "Medication safety"],
    ["findings", "Findings"],
    ["clinical_findings", "Clinical findings"],
    ["evidence_summary", "Evidence summary"],
    ["clinician_actions", "Clinician actions"],
    ["missing_information", "Missing information"],
    ["limitations", "Limitations"],
    ["citations", "Citations"]
  ];

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[char]));
  }

  function readReport(card) {
    try {
      return JSON.parse(card.querySelector("[data-editable-report]")?.textContent || "{}");
    } catch {
      return {};
    }
  }

  function renderEditor(card) {
    const host = card.querySelector("[data-report-editor-fields]");
    if (!host) return;
    const report = readReport(card);
    const fields = scalarFields.map(([name, label]) => `
      <label class="report-editor-field"><span>${escapeHtml(label)}</span>
        <textarea rows="${name.includes("summary") ? 4 : 2}" data-report-field="${name}">${escapeHtml(report[name] || "")}</textarea>
      </label>`).join("");
    const lists = listFields.map(([name, label]) => `
      <label class="report-editor-field"><span>${escapeHtml(label)} <small>(one item per line)</small></span>
        <textarea rows="4" data-report-list-field="${name}">${escapeHtml((report[name] || []).join("\n"))}</textarea>
      </label>`).join("");
    host.innerHTML = fields + lists;
  }

  function setEditorOpen(card, open) {
    const editor = card.querySelector("[data-report-editor]");
    if (!editor) return;
    if (open) renderEditor(card);
    editor.hidden = !open;
    card.classList.toggle("is-report-editing", open);
    card.querySelector("[data-report-edit-toggle]")?.setAttribute("aria-expanded", String(open));
  }

  document.addEventListener("click", event => {
    const toggle = event.target.closest("[data-report-edit-toggle]");
    if (!toggle) return;
    const card = toggle.closest(".submission");
    if (card) setEditorOpen(card, card.querySelector("[data-report-editor]")?.hidden !== false);
  });

  document.addEventListener("click", event => {
    const cancel = event.target.closest("[data-report-edit-cancel]");
    if (!cancel) return;
    const card = cancel.closest(".submission");
    if (card) setEditorOpen(card, false);
  });

  document.addEventListener("click", async event => {
    const save = event.target.closest("[data-report-edit-save]");
    if (!save) return;
    const card = save.closest(".submission");
    if (!card) return;
    const status = card.querySelector("[data-report-edit-status]");
    const report = readReport(card);
    card.querySelectorAll("[data-report-field]").forEach(input => {
      report[input.dataset.reportField] = input.value.trim();
    });
    card.querySelectorAll("[data-report-list-field]").forEach(input => {
      report[input.dataset.reportListField] = input.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
    });
    save.disabled = true;
    if (status) status.textContent = "Saving report...";
    try {
      const response = await fetch("report-chat/report-edit", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submission_id: card.dataset.submissionId, report })
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
      card.querySelector("[data-editable-report]").textContent = JSON.stringify(payload.report || report);
      const reportContent = card.querySelector("[data-ai-report-content]");
      if (reportContent && payload.ai_html) reportContent.innerHTML = payload.ai_html;
      const revision = payload.patch_entry?.created_at || new Date().toISOString();
      card.dataset.reportRevision = revision;
      const time = card.querySelector("[data-report-time]");
      if (time) time.setAttribute("datetime", revision);
      setEditorOpen(card, false);
      if (status) status.textContent = "Report saved.";
      updateReportTimes();
    } catch (error) {
      if (status) status.textContent = error.message || "Could not save report.";
    } finally {
      save.disabled = false;
    }
  });

  function parsedDate(value) {
    if (!value) return null;
    const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function relativeCreated(date) {
    const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
    if (seconds < 45) return "Created just now";
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `Created ${minutes} min${minutes === 1 ? "" : "s"} ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `Created ${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.round(hours / 24);
    return `Created ${days} day${days === 1 ? "" : "s"} ago`;
  }

  function updateReportTimes() {
    document.querySelectorAll("[data-report-time]").forEach(time => {
      const date = parsedDate(time.getAttribute("datetime"));
      if (!date) return;
      const exact = time.querySelector("[data-exact-time]");
      const relative = time.querySelector("[data-relative-time]");
      if (exact) exact.textContent = new Intl.DateTimeFormat(undefined, {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short"
      }).format(date);
      if (relative) relative.textContent = relativeCreated(date);
    });
  }

  function currentPollState() {
    return Array.from(document.querySelectorAll(".submission[data-submission-id]")).map(card => ({
      id: Number(card.dataset.submissionId), revision: card.dataset.reportRevision || ""
    }));
  }

  async function pollSubmissions() {
    if (document.body.classList.contains("report-chat-body")) return;
    try {
      const response = await fetch("submissions/poll", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      const remote = Array.isArray(payload.submissions) ? payload.submissions : [];
      const local = currentPollState();
      const changed = remote.length !== local.length || remote.some((item, index) => {
        return !local[index] || item.id !== local[index].id || String(item.revision || "") !== local[index].revision;
      });
      if (changed && !document.querySelector(".submission.is-report-editing")) window.location.reload();
    } catch {
      // SSE remains the primary notification channel; the next poll retries quietly.
    }
  }

  updateReportTimes();
  window.setInterval(updateReportTimes, 30000);
  window.setInterval(pollSubmissions, 15000);
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
    "/report-chat": "Report Chat",
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
      if (href === "submissions") return activePath === "/submissions" || activePath === "/report-chat";
      const form = formNav.find(item => item.href === href);
      return form ? available.has(form.key) : true;
    });
  }

  function progressStepIndex(activePath) {
    if (activePath === "/submissions" || activePath === "/report-chat") return formNav.length + 1;
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
    if (activePath === "/submissions" || activePath === "/report-chat") return 100;
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
      const activeClass = activePath === linkPath || (activePath === "/report-chat" && linkPath === "/submissions") ? " is-active" : "";
      return `<a class="nv-nav-link${activeClass}" href="${navHref(href)}">${icon(pathData)}<span>${label}</span></a>`;
    }).join("");
    const sidebarCredit = activePath === "/submissions" || activePath === "/report-chat" ? "" : `
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
    if (document.body.classList.contains("report-chat-body")) return;
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
