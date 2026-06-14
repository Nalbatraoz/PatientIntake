function getCheckedValue(name) {
  const el = document.querySelector(`[name="${name}"]:checked`);
  return el ? el.value : null;
}

function isChoice(type) { return type === "checkbox" || type === "radio"; }

// Purpose: validation rules for required form fields.
const REQUIRED_FIELDS = [

  // Purpose: visit type must be selected before the questionnaire is shown.
  { name: "visitType", label: "Visit Type / نوع الزيارة", type: "radio" },

  { name: "patientStatus", label: "Patient Status / حالة المريض", type: "radio" },

  // Purpose: personal information fields.
  { name: "codeNo",      label: "Code / الكود",                         type: "text"   },
  { name: "fullName",    label: "Name / الاسم",                         type: "text"   },
  { name: "age",         label: "Age / السن",                           type: "number", extra: { min: 1, max: 120 } },
  { name: "nationality", label: "Nationality / الجنسية",                type: "text"   },
  { name: "occupation",  label: "Occupation / الوظيفة",                 type: "text"   },
  { name: "mobile",      label: "Phone / الهاتف",                       type: "text"   },
  { name: "email",       label: "Email / البريد الإلكتروني",             type: "email"  },

  // Purpose: marital and family history fields.
  { name: "maritalStatus",         label: "Marital Status / الحالة الاجتماعية",                                  type: "radio" },
  { name: "durationMarriage",      label: "Duration of Marriage / مدة الزواج",                                   type: "text"  },
  { name: "numberWives",           label: "Number of Wives / عدد الزوجات",                                       type: "text"  },
  { name: "numberChildren",        label: "Number of Children / عدد الأبناء",                                    type: "text"  },
  { name: "youngestChildAge",      label: "Age of Youngest Child / سن أصغر الأبناء",                             type: "text"  },
  { name: "willingConceive",       label: "Willing to Conceive? / الرغبة في الإنجاب",                            type: "radio" },
  { name: "previousConceiveTrials",label: "Previous Trials to Conceive / محاولات سابقة للإنجاب",                 type: "text"  },
  { name: "contraceptionMethods",  label: "Methods of Contraception / وسائل منع الحمل",                         type: "text"  },
  { name: "divorceRelated",        label: "Divorce related to complaint? / هل الطلاق مرتبط بالشكوى؟",           type: "radio" },

  // Purpose: allergy fields.
  { name: "drugAllergies",  label: "Drug Allergies / حساسية الأدوية",   type: "text" },
  { name: "otherAllergies", label: "Other Allergies / حساسية أخرى",     type: "text" },

  // Purpose: referral source field.
  { name: "referral", label: "How did you know about us? / كيف تعرفت علينا؟", type: "checkbox" },

  // Purpose: lifestyle and habit fields.
  { name: "sleepHours",           label: "Average sleep hours / متوسط ساعات النوم",          type: "text"     },
  { name: "sleepType",            label: "Type of sleep / طبيعة النوم",                      type: "radio"    },
  { name: "sleepQuality",         label: "Sleep quality 1-10 / جودة النوم",                  type: "number",   extra: { min: 1, max: 10 } },
  { name: "snoring",              label: "Snoring or apnea? / شخير أو انقطاع نفس؟",          type: "radio"    },
  { name: "daytimeFatigue",       label: "Daytime fatigue? / خمول نهاري؟",                   type: "radio"    },
  { name: "exerciseFrequency",    label: "Exercise frequency / معدل الرياضة",                type: "text"     },
  { name: "exerciseType",         label: "Type of exercise / نوع الرياضة",                   type: "checkbox" },
  { name: "sittingHours",         label: "Sitting hours per day / ساعات الجلوس",             type: "text"     },
  { name: "weight",               label: "Weight / الوزن",                                   type: "text"     },
  { name: "height",               label: "Height / الطول",                                   type: "text"     },
  { name: "bmi",                  label: "BMI / مؤشر كتلة الجسم",                            type: "text"     },
  { name: "waist",                label: "Waist Circumference / محيط الخصر",                 type: "text"     },
  { name: "lateNightEating",      label: "Late night eating / الأكل المتأخر",                type: "radio"    },
  { name: "smokingStatus",        label: "Smoking Status / حالة التدخين",                    type: "radio"    },
  { name: "cigarettesPerDay",     label: "Cigarettes per day / عدد السجائر يومياً",           type: "text"     },
  { name: "alcohol",              label: "Alcohol consumption / تناول الكحول",               type: "radio"    },
  { name: "recreationalDrugUse",  label: "Recreational drug use / مواد ترفيهية",             type: "radio"    },
  { name: "pornographyFrequency", label: "Pornography frequency / محتوى إباحي",              type: "radio"    },
  { name: "masturbation",         label: "Masturbation / العادة السرية",                     type: "radio"    },
  { name: "partnerDifficultyOnly",label: "Difficulty with partner only? / صعوبة مع الشريك فقط؟", type: "radio" },

  // Purpose: psychological and recovery fields.
  { name: "stressLevel",          label: "Stress level 1-10 / مستوى الضغوط",                type: "number", extra: { min: 1, max: 10 } },
  { name: "anxietyDepression",    label: "Anxiety/Depression diagnosis? / تشخيص قلق أو اكتئاب؟", type: "radio" },
  { name: "relationshipConflict", label: "Major relationship conflict? / خلافات زوجية حادة؟",     type: "radio" },
  { name: "performanceAnxiety",   label: "Performance anxiety? / قلق الأداء؟",              type: "radio"  },
  { name: "sedentaryWork",        label: "Mostly sedentary work? / عمل مكتبي؟",             type: "radio"  },
  { name: "nightShifts",          label: "Night shifts? / مناوبات ليلية؟",                  type: "radio"  },
  { name: "heatToxinExposure",    label: "Heat/Toxin exposure? / تعرض للحرارة أو السموم؟",  type: "radio"  },
  { name: "energyLevel",          label: "Energy level 1-10 / مستوى الطاقة",                type: "number", extra: { min: 1, max: 10 } },
  { name: "libidoScore",          label: "Libido 1-10 / الرغبة الجنسية",                    type: "number", extra: { min: 1, max: 10 } },
  { name: "recoveryScore",        label: "Recovery 1-10 / التعافي البدني",                  type: "number", extra: { min: 1, max: 10 } },

  // Purpose: primary complaint field.
  { name: "complaints", label: "Primary Complaints / الشكوى الرئيسية", type: "checkbox" },
];

// Purpose: remember which fields can show live validation.
const touched       = new Set();
let   submitAttempted = false;

// Purpose: small DOM helpers used by validation and uploads.
function getField(name) {
  return document.querySelector(`[name="${name}"]`);
}

function getAllFields(name) {
  return Array.from(document.querySelectorAll(`[name="${name}"]`));
}

function updateQuestionVisibility() {
  const form = document.getElementById("intakeForm");
  if (!form) return;

  const hasVisitType = Boolean(getCheckedValue("visitType"));
  const hasPatientCode = form.dataset.patientReady === "true";
  form.classList.toggle("sections-locked", !hasVisitType);
  form.classList.toggle("patient-unresolved", hasVisitType && !hasPatientCode);
}

function getErrorAnchor(name, type) {
  if (isChoice(type)) {
    const first = getField(name);
    if (!first) return null;
    const group = first.closest(".grid, .radio-group");
    if (!group) return first.parentElement;
    return group.closest(".field-wrapper") || group;
  }
  return getField(name) || null;
}

// Purpose: render or clear one inline validation error.
function setError(name, type, message) {
  const anchor = getErrorAnchor(name, type);
  if (!anchor) return;

  const fields = isChoice(type) ? getAllFields(name) : [getField(name)].filter(Boolean);
  fields.forEach(el => el.classList.toggle("input-error", !!message));

  const isWrapper = anchor.classList.contains("field-wrapper");
  if (isWrapper) anchor.classList.toggle("field-wrapper-error", !!message);

  const errorId = `err-${name}`;
  let errEl = document.getElementById(errorId);

  if (message) {
    if (!errEl) {
      errEl = document.createElement("p");
      errEl.id        = errorId;
      errEl.className = "field-error";
      if (isWrapper) anchor.appendChild(errEl);
      else anchor.insertAdjacentElement("afterend", errEl);
    }
    errEl.textContent = message;
  } else {
    if (errEl) errEl.remove();
    if (isWrapper) anchor.classList.remove("field-wrapper-error");
  }
}

// Purpose: validate one active rule and return its error message.
function validateRule({ name, label, type, extra, when }) {
  if (when && !when()) return "";

  if (type === "checkbox") {
    return getAllFields(name).some(el => el.checked)
      ? ""
      : `Please select at least one option / اختر خياراً واحداً على الأقل`;
  }

  if (type === "radio") {
    return getAllFields(name).some(el => el.checked)
      ? ""
      : `Please choose an option / اختر إجابة`;
  }

  const el = getField(name);
  if (!el) return "";
  const val = el.value.trim();

  if (!val) return `This field is required / هذا الحقل مطلوب`;

  if (type === "email") {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)
      ? ""
      : `Please enter a valid email / أدخل بريداً إلكترونياً صحيحاً`;
  }

  if (type === "number") {
    const num = Number(val);
    if (isNaN(num)) return `Please enter a valid number / أدخل رقماً صحيحاً`;
    if (extra?.min !== undefined && num < extra.min) return `Minimum value is ${extra.min}`;
    if (extra?.max !== undefined && num > extra.max) return `Maximum value is ${extra.max}`;
  }

  return "";
}

// Purpose: revalidate fields after user interaction.
function revalidate(name) {
  if (!submitAttempted && !touched.has(name)) return;
  const rule = REQUIRED_FIELDS.find(r => r.name === name);
  if (!rule) return;
  setError(name, rule.type, validateRule(rule));
}

function revalidateConditionals() {
  if (!submitAttempted) return;
  REQUIRED_FIELDS
    .filter(rule => rule.when)
    .forEach(rule => setError(rule.name, rule.type, rule.when() ? validateRule(rule) : ""));
}

// Purpose: attach live validation listeners to each required field.
REQUIRED_FIELDS.forEach(rule => {
  const { name, type } = rule;

  if (isChoice(type)) {
    getAllFields(name).forEach(el => {
      el.addEventListener("change", () => {
        touched.add(name);
        revalidate(name);
        revalidateConditionals();
      });
    });
    return;
  }

  const el = getField(name);
  if (!el) return;

  const ev = el.tagName === "SELECT" ? "change" : "input";
  el.addEventListener(ev, () => {
    touched.add(name);
    revalidate(name);
    revalidateConditionals();
  });
  el.addEventListener("blur", () => {
    touched.add(name);
    revalidate(name);
  });
});

getAllFields("visitType").forEach(el => {
  el.addEventListener("change", updateQuestionVisibility);
});
updateQuestionVisibility();

// Purpose: gather uploads, scan medication evidence, then submit the form.
const formElement = document.getElementById("intakeForm");
formElement.noValidate = true;
const submitButton = document.getElementById("submitButton");
const submitStatus = document.getElementById("submitStatus");

const drugImageInput = document.getElementById("drugImageFiles");
const investigationFileInput = document.getElementById("investigationFiles");
const drugImagePreview = document.getElementById("drugImagePreview");
const investigationFileList = document.getElementById("investigationFileList");
const scanDrugsButton = document.getElementById("scanDrugsButton");
const scanStatus = document.getElementById("scanStatus");
const scanResults = document.getElementById("scanResults");
const uploadedDrugAnalysisInput = document.getElementById("uploadedDrugAnalysis");
const uploadedFilesInput = document.getElementById("uploadedFiles");
const uploadedFileSummaryInput = document.getElementById("uploadedFileSummary");
const currentMedicationsInput = document.getElementById("currentMedications");
const medicalHistoryInput = document.getElementById("medicalHistory");
const investigationResultsInput = document.getElementById("investigationResults");
const firstTimePanel = document.getElementById("firstTimePanel");
const existingPatientPanel = document.getElementById("existingPatientPanel");
const existingPatientCodeInput = document.getElementById("existingPatientCode");
const patientPasswordCreateInput = document.getElementById("patientPasswordCreate");
const patientPasswordConfirmInput = document.getElementById("patientPasswordConfirm");
const existingPatientPasswordInput = document.getElementById("existingPatientPassword");
const patientPasswordInput = getField("patientPassword");
const generateCodeButton = document.getElementById("generateCodeButton");
const findPatientButton = document.getElementById("findPatientButton");
const patientCodeStatus = document.getElementById("patientCodeStatus");
const codeNoInput = getField("codeNo");

let previewObjectUrls = [];
let latestScanSignature = "";
let latestScanResult = null;
let isSubmitting = false;

function setPatientReady(ready) {
  formElement.dataset.patientReady = ready ? "true" : "false";
  updateQuestionVisibility();
}

function updatePatientStatusPanels() {
  const status = getCheckedValue("patientStatus");
  if (firstTimePanel) firstTimePanel.hidden = status !== "first_time";
  if (existingPatientPanel) existingPatientPanel.hidden = status !== "existing";
}

function setStoredPatientPassword(password) {
  if (patientPasswordInput) {
    patientPasswordInput.value = String(password || "");
  }
}

function clearPatientPasswordFields() {
  if (patientPasswordInput) patientPasswordInput.value = "";
  if (patientPasswordCreateInput) patientPasswordCreateInput.value = "";
  if (patientPasswordConfirmInput) patientPasswordConfirmInput.value = "";
  if (existingPatientPasswordInput) existingPatientPasswordInput.value = "";
}

function getVisiblePatientPassword() {
  const status = getCheckedValue("patientStatus");
  if (status === "first_time") {
    return {
      password: patientPasswordCreateInput?.value.trim() || "",
      confirm: patientPasswordConfirmInput?.value.trim() || "",
    };
  }
  if (status === "existing") {
    return {
      password: existingPatientPasswordInput?.value.trim() || "",
      confirm: "",
    };
  }
  return { password: "", confirm: "" };
}

function validatePasswordCapture() {
  const status = getCheckedValue("patientStatus");
  if (status === "first_time") {
    const password = patientPasswordCreateInput?.value.trim() || "";
    const confirm = patientPasswordConfirmInput?.value.trim() || "";
    if (!password) {
      showMessage("Password Required", "Create a private password before generating the patient code.", patientPasswordCreateInput);
      return false;
    }
    if (password.length < 8) {
      showMessage("Password Too Short", "Use at least 8 characters for the patient password.", patientPasswordCreateInput);
      return false;
    }
    if (password !== confirm) {
      showMessage("Password Mismatch", "The password and confirmation do not match.", patientPasswordConfirmInput);
      return false;
    }
    setStoredPatientPassword(password);
    return true;
  }

  if (status === "existing") {
    const password = existingPatientPasswordInput?.value.trim() || "";
    if (!password) {
      showMessage("Password Required", "Enter the patient password to open this record.", existingPatientPasswordInput);
      return false;
    }
    setStoredPatientPassword(password);
    return true;
  }

  return true;
}

function fillFormFromSavedData(data) {
  Object.entries(data || {}).forEach(([key, value]) => {
    if (["clinical_pipeline", "visitType", "patientStatus"].includes(key)) return;

    const fields = getAllFields(key);
    if (!fields.length) return;

    const first = fields[0];
    if (first.type === "file") return;

    if (first.type === "radio") {
      fields.forEach(field => { field.checked = String(field.value) === String(value); });
      return;
    }

    if (first.type === "checkbox") {
      const values = Array.isArray(value) ? value.map(String) : [String(value)];
      fields.forEach(field => { field.checked = values.includes(String(field.value)); });
      return;
    }

    first.value = Array.isArray(value) ? value.join(", ") : String(value ?? "");
  });
}

async function generatePatientCode() {
  if (!validatePasswordCapture()) {
    return;
  }
  if (generateCodeButton) generateCodeButton.disabled = true;
  if (patientCodeStatus) patientCodeStatus.textContent = "Generating patient code...";
  try {
    const response = await fetch("/patient-code/next");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not generate patient code.");
    if (codeNoInput) codeNoInput.value = payload.codeNo;
    if (patientPasswordInput) patientPasswordInput.value = patientPasswordCreateInput?.value.trim() || "";
    setPatientReady(true);
    if (patientCodeStatus) patientCodeStatus.textContent = `Generated patient code: ${payload.codeNo}`;
    document.querySelector("section:not(.visit-type-section):not(.patient-status-section)")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setPatientReady(false);
    showMessage("Patient Code Error", error.message || "Could not generate patient code.", generateCodeButton);
  } finally {
    if (generateCodeButton) generateCodeButton.disabled = false;
  }
}

async function findExistingPatient() {
  const code = existingPatientCodeInput?.value.trim();
  if (!code) {
    showMessage("Patient Code Required", "Enter the existing patient code before searching.", existingPatientCodeInput);
    return;
  }

  if (!validatePasswordCapture()) {
    return;
  }

  if (findPatientButton) findPatientButton.disabled = true;
  if (patientCodeStatus) patientCodeStatus.textContent = "Searching patient code...";
  try {
    const response = await fetch("/patient-code/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        codeNo: code,
        password: existingPatientPasswordInput?.value.trim() || "",
      }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.found) {
      throw new Error(payload.error || `No patient found for code ${code}.`);
    }
    fillFormFromSavedData(payload.form_data);
    if (codeNoInput) codeNoInput.value = payload.codeNo;
    if (patientPasswordInput) patientPasswordInput.value = existingPatientPasswordInput?.value.trim() || "";
    setPatientReady(true);
    if (patientCodeStatus) patientCodeStatus.textContent = `Found existing patient code: ${payload.codeNo}`;
    document.querySelector("section:not(.visit-type-section):not(.patient-status-section)")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setPatientReady(false);
    if (patientCodeStatus) patientCodeStatus.textContent = "";
    showMessage("Patient Not Found", error.message || "Could not find that patient code.", findPatientButton);
  } finally {
    if (findPatientButton) findPatientButton.disabled = false;
  }
}

getAllFields("patientStatus").forEach(el => {
  el.addEventListener("change", () => {
    setPatientReady(false);
    if (codeNoInput) codeNoInput.value = "";
    clearPatientPasswordFields();
    updatePatientStatusPanels();
    if (patientCodeStatus) patientCodeStatus.textContent = "";
  });
});

generateCodeButton?.addEventListener("click", generatePatientCode);
findPatientButton?.addEventListener("click", findExistingPatient);
existingPatientCodeInput?.addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    findExistingPatient();
  }
});
existingPatientPasswordInput?.addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    findExistingPatient();
  }
});
updatePatientStatusPanels();
setPatientReady(false);

function setSubmitState(active, message = "") {
  isSubmitting = active;
  if (submitButton) {
    submitButton.disabled = active;
    submitButton.textContent = active ? "Submitting..." : "Submit / إرسال";
    submitButton.setAttribute("aria-busy", active ? "true" : "false");
  }
  if (submitStatus) submitStatus.textContent = message;
}

function selectedFiles(input) {
  return input?.files ? Array.from(input.files) : [];
}

function selectedUploadFiles() {
  return [
    ...selectedFiles(drugImageInput),
    ...selectedFiles(investigationFileInput),
  ];
}

function uploadFileSummary() {
  return {
    drugImages: selectedFiles(drugImageInput).map(file => ({
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
    })),
    investigationFiles: selectedFiles(investigationFileInput).map(file => ({
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
    })),
  };
}

function updateUploadFileSummary() {
  if (!uploadedFileSummaryInput) return;
  uploadedFileSummaryInput.value = JSON.stringify(uploadFileSummary());
}

function uploadSignature() {
  const files = selectedUploadFiles()
    .map(file => `${file.name}:${file.size}:${file.lastModified}`)
    .join("|");
  return [
    files,
    currentMedicationsInput?.value || "",
    medicalHistoryInput?.value || "",
    investigationResultsInput?.value || "",
  ].join("::");
}

function hasSelectedUploadFiles() {
  return selectedUploadFiles().length > 0;
}

function resetScanState() {
  latestScanSignature = "";
  latestScanResult = null;
  if (uploadedDrugAnalysisInput) uploadedDrugAnalysisInput.value = "";
  if (uploadedFilesInput) uploadedFilesInput.value = "";
  if (scanResults) {
    scanResults.hidden = true;
    scanResults.innerHTML = "";
  }
  if (scanStatus) scanStatus.textContent = "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderDrugImagePreview() {
  if (!drugImagePreview) return;
  previewObjectUrls.forEach(url => URL.revokeObjectURL(url));
  previewObjectUrls = [];
  drugImagePreview.innerHTML = "";

  selectedFiles(drugImageInput).forEach(file => {
    const item = document.createElement("div");
    item.className = "upload-preview-item";

    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      const url = URL.createObjectURL(file);
      previewObjectUrls.push(url);
      image.src = url;
      image.alt = file.name;
      item.appendChild(image);
    }

    const name = document.createElement("span");
    name.textContent = file.name;
    item.appendChild(name);
    drugImagePreview.appendChild(item);
  });
}

function renderInvestigationFileList() {
  if (!investigationFileList) return;
  const files = selectedFiles(investigationFileInput);
  investigationFileList.innerHTML = files
    .map(file => `<span>${escapeHtml(file.name)}</span>`)
    .join("");
}

function compactList(values) {
  if (!Array.isArray(values) || !values.length) return "";
  return values.map(value => escapeHtml(value)).join(", ");
}

function renderScanResults(result) {
  if (!scanResults) return;

  const candidates = result.drug_candidates?.length
    ? result.drug_candidates.map(name => `<li>${escapeHtml(name)}</li>`).join("")
    : "<li>No medication names detected / لم يتم اكتشاف أسماء أدوية. Add names manually in Current Medications and scan again / أضف الأسماء يدويًا في خانة الأدوية الحالية ثم أعد الفحص.</li>";

  const openFdaItems = (result.openfda || []).map(item => {
    if (!item.found) {
      return `
        <article class="scan-result-item">
          <h3>${escapeHtml(item.query)}</h3>
          <p>${escapeHtml(item.message || item.error || "No openFDA match found.")}</p>
        </article>
      `;
    }

    const label = item.label || {};
    return `
      <article class="scan-result-item">
        <h3>${escapeHtml(item.query)}</h3>
        <dl>
          <dt>Brand / الاسم التجاري</dt><dd>${compactList(label.brand_names) || "Not listed / غير مذكور"}</dd>
          <dt>Generic / الاسم العلمي</dt><dd>${compactList(label.generic_names) || "Not listed / غير مذكور"}</dd>
          <dt>Manufacturer / الشركة المصنعة</dt><dd>${compactList(label.manufacturer_names) || "Not listed / غير مذكور"}</dd>
          <dt>Route / طريقة الاستخدام</dt><dd>${compactList(label.routes) || "Not listed / غير مذكور"}</dd>
        </dl>
        ${label.warnings ? `<p><strong>Warnings / التحذيرات:</strong> ${escapeHtml(label.warnings)}</p>` : ""}
        ${label.contraindications ? `<p><strong>Contraindications / موانع الاستخدام:</strong> ${escapeHtml(label.contraindications)}</p>` : ""}
        ${label.drug_interactions ? `<p><strong>Drug interactions / التداخلات الدوائية:</strong> ${escapeHtml(label.drug_interactions)}</p>` : ""}
      </article>
    `;
  }).join("");

  const flags = result.label_flags?.length
    ? `
      <div class="scan-alerts">
        <h3>Review Flags / تنبيهات للمراجعة</h3>
        <ul>${result.label_flags.map(flag => `<li>${escapeHtml(flag.message)}</li>`).join("")}</ul>
      </div>
    `
    : "";

  const drugBank = result.drugbank?.configured
    ? `<p class="scan-meta">DrugBank lookup enabled / تم تفعيل بحث DrugBank. Interaction matches / عدد التداخلات: ${escapeHtml(result.drugbank.interactions?.length || 0)}</p>`
    : `<p class="scan-meta">${escapeHtml(result.drugbank?.message || "DrugBank is not configured.")}</p>`;

  const notes = result.notes?.length
    ? `<ul class="scan-notes">${result.notes.map(note => `<li>${escapeHtml(note)}</li>`).join("")}</ul>`
    : "";

  scanResults.innerHTML = `
    <div class="scan-summary">
      <div>
        <h3>Detected Medication Names / أسماء الأدوية المكتشفة</h3>
        <ul>${candidates}</ul>
      </div>
      <div>
        <h3>Lookup Source / مصدر البحث</h3>
        <p>${escapeHtml(result.scan_source || "manual_text")}</p>
        ${drugBank}
      </div>
    </div>
    ${flags}
    <div class="scan-result-list">${openFdaItems}</div>
    ${notes}
  `;
  scanResults.hidden = false;
}

async function scanDrugUploads() {
  const hasManualContext = Boolean(
    currentMedicationsInput?.value.trim() ||
    medicalHistoryInput?.value.trim() ||
    investigationResultsInput?.value.trim()
  );

  if (!hasSelectedUploadFiles() && !hasManualContext) {
    showMessage(
      "Nothing to Scan / لا يوجد ما يمكن فحصه",
      "Add a drug photo or medication text before scanning.\nأضف صورة دواء أو اكتب أسماء الأدوية قبل بدء الفحص.",
      scanDrugsButton
    );
    return false;
  }

  const formData = new FormData();
  selectedFiles(drugImageInput).forEach(file => formData.append("drugImages", file));
  selectedFiles(investigationFileInput).forEach(file => formData.append("investigationFiles", file));
  formData.append("currentMedications", currentMedicationsInput?.value || "");
  formData.append("medicalHistory", medicalHistoryInput?.value || "");
  formData.append("investigationResults", investigationResultsInput?.value || "");

  const signature = uploadSignature();
  scanDrugsButton.disabled = true;
  scanStatus.textContent = "Scanning uploads and checking medication labels... / جارٍ فحص الملفات ومراجعة بيانات الأدوية...";

  try {
    const response = await fetch("/scan-drugs", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Scan failed.");

    latestScanSignature = signature;
    latestScanResult = result;
    if (uploadedDrugAnalysisInput) uploadedDrugAnalysisInput.value = JSON.stringify(result);
    if (uploadedFilesInput) uploadedFilesInput.value = JSON.stringify(result.files || []);
    renderScanResults(result);
    scanStatus.textContent = result.message || "Scan complete / تم الفحص.";
    return true;
  } catch (error) {
    scanStatus.textContent = "Scan failed.";
    showMessage(
      "Upload Scan Error / خطأ في فحص الملفات",
      `${error.message || "Could not scan the uploaded files."}\nPlease make sure the server is running and try again.\nتعذر فحص الملفات. تأكد أن الخادم يعمل ثم حاول مرة أخرى.`,
      scanDrugsButton
    );
    return false;
  } finally {
    scanDrugsButton.disabled = false;
  }
}

async function ensureUploadFilesAreScanned() {
  if (!hasSelectedUploadFiles()) return true;
  if (latestScanResult && latestScanSignature === uploadSignature()) return true;
  return scanDrugUploads();
}

drugImageInput?.addEventListener("change", () => {
  renderDrugImagePreview();
  updateUploadFileSummary();
  resetScanState();
});

investigationFileInput?.addEventListener("change", () => {
  renderInvestigationFileList();
  updateUploadFileSummary();
  resetScanState();
});

[currentMedicationsInput, medicalHistoryInput, investigationResultsInput].forEach(el => {
  el?.addEventListener("input", () => {
    updateUploadFileSummary();
    if (latestScanResult) resetScanState();
  });
});

scanDrugsButton?.addEventListener("click", scanDrugUploads);
updateUploadFileSummary();

function formatPipelineMessage(result) {
  const submissionId = result?.submission_id || result?.pipeline?.submission_id;
  const codeNo = result?.codeNo;
  const lines = ["Form submitted successfully."];
  if (codeNo) lines.push(`Patient Code: ${codeNo}`);
  if (submissionId) lines.push(`Submission #${submissionId}`);
  return lines.join("\n\n");
}

function getComplaintSelections() {
  return getAllFields("complaints")
    .filter(field => field.checked)
    .map(field => String(field.value || "").trim())
    .filter(Boolean);
}

formElement.addEventListener("submit", async function (e) {
  e.preventDefault();
  if (isSubmitting) return;
  submitAttempted = true;

  let firstAnchor = null;
  let hasErrors   = false;

  REQUIRED_FIELDS.forEach(rule => {
    const err = validateRule(rule);
    setError(rule.name, rule.type, err);
    if (err && !firstAnchor) firstAnchor = getErrorAnchor(rule.name, rule.type);
    if (err) hasErrors = true;
  });

  if (hasErrors) {
    if (firstAnchor) firstAnchor.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  if (!validatePasswordCapture()) {
    return;
  }

  const capturedPassword = getVisiblePatientPassword().password;
  if (patientPasswordInput) {
    patientPasswordInput.value = capturedPassword;
  }

  setSubmitState(true, "Submitting form and running the clinical workflow. Please wait...");
  try {
    const uploadsReady = await ensureUploadFilesAreScanned();
    if (!uploadsReady) return;

    const data = buildFormData(this);
    const response = await fetch("/submit", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Submission failed.");
    const submissionId = result.submission_id;
    const fullName = getField("fullName")?.value || "";
    const age = getField("age")?.value || "";
    const phone = getField("mobile")?.value || "";
    const email = getField("email")?.value || "";
    const codeNo = result.codeNo || `INT-${submissionId}`;
    const complaints = getComplaintSelections().join(",");

    // Redirect to IIEF page, passing submission metadata
    window.location.href = `/iief?submission_id=${submissionId}&codeNo=${encodeURIComponent(codeNo)}&name=${encodeURIComponent(fullName)}&age=${encodeURIComponent(age)}&phone=${encodeURIComponent(phone)}&email=${encodeURIComponent(email)}&complaints=${encodeURIComponent(complaints)}`;
  } catch (error) {
    showMessage(
      "Submission Error / خطأ في الإرسال",
      `${error.message || "Could not submit the form."}\nPlease make sure the server is running.`
    );
  } finally {
    setSubmitState(false);
  }
});

// Purpose: turn form controls into the JSON payload expected by Flask.
function buildFormData(form) {
  const data = {};
  new FormData(form).forEach((value, key) => {
    if (value instanceof File) return;

    if (data[key]) {
      if (!Array.isArray(data[key])) data[key] = [data[key]];
      data[key].push(value);
    } else {
      data[key] = value;
    }
  });

  ["uploadedDrugAnalysis", "uploadedFiles", "uploadedFileSummary"].forEach(key => {
    if (typeof data[key] !== "string" || !data[key].trim()) return;
    try {
      data[key] = JSON.parse(data[key]);
    } catch {
      // Purpose: leave unparsed values intact so the form still submits.
    }
  });

  return data;
}

// Purpose: simple reusable modal for validation and submission messages.
let messageDialog = null;

function getMessageDialog() {
  if (messageDialog) return messageDialog;

  const overlay = document.createElement("div");
  overlay.className = "message-overlay";
  overlay.hidden    = true;
  overlay.innerHTML = `
    <div class="message-dialog" role="dialog" aria-modal="true" aria-labelledby="messageTitle">
      <h2 id="messageTitle"></h2>
      <p id="messageBody"></p>
      <button type="button" id="messageOk">OK</button>
    </div>
  `;
  document.body.appendChild(overlay);

  const title  = overlay.querySelector("#messageTitle");
  const body   = overlay.querySelector("#messageBody");
  const okBtn  = overlay.querySelector("#messageOk");
  let returnEl = null;

  function close() {
    overlay.hidden = true;
    if (returnEl?.focus) returnEl.focus({ preventScroll: true });
  }

  okBtn.addEventListener("click", close);
  overlay.addEventListener("click", ev => { if (ev.target === overlay) close(); });
  document.addEventListener("keydown", ev => { if (!overlay.hidden && ev.key === "Escape") close(); });

  messageDialog = { overlay, title, body, okBtn, setReturnFocus(el) { returnEl = el; } };
  return messageDialog;
}

function showMessage(title, message, returnFocusEl) {
  const d = getMessageDialog();
  d.title.textContent = title;
  d.body.textContent  = message;
  d.setReturnFocus(returnFocusEl);
  d.overlay.hidden = false;
  d.okBtn.focus();
}

// Camera Capture Module JavaScript
(function() {
  const cameraTriggerBtn = document.getElementById("cameraTriggerBtn");
  const cameraModal = document.getElementById("cameraModal");
  const cameraCloseBtn = document.getElementById("cameraCloseBtn");
  const cameraVideo = document.getElementById("cameraVideo");
  const cameraCanvas = document.getElementById("cameraCanvas");
  const cameraFlash = document.getElementById("cameraFlash");
  const cameraDeviceSelectWrapper = document.getElementById("cameraDeviceSelectWrapper");
  const cameraDeviceSelect = document.getElementById("cameraDeviceSelect");
  const cameraCaptureBtn = document.getElementById("cameraCaptureBtn");
  const cameraStatusMsg = document.getElementById("cameraStatusMsg");
  const drugImageInput = document.getElementById("drugImageFiles");

  if (!cameraTriggerBtn || !cameraModal) return;

  let cameraStream = null;
  let currentDeviceId = null;
  let camerasList = [];
  let capturedPhotosCount = 0;

  function updateCameraStatus(msg, isError = false) {
    if (!cameraStatusMsg) return;
    cameraStatusMsg.textContent = msg;
    cameraStatusMsg.style.color = isError ? "#dc2626" : "#10b981";
  }

  async function startStream(deviceId) {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
    }

    const constraints = {
      video: deviceId
        ? { deviceId: { exact: deviceId } }
        : { facingMode: "environment" }
    };

    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    if (cameraVideo) {
      cameraVideo.srcObject = cameraStream;
    }
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      cameraStream = null;
    }
    if (cameraVideo) {
      cameraVideo.srcObject = null;
    }
    cameraModal.hidden = true;
  }

  async function initCamera() {
    updateCameraStatus("Initializing camera... / جاري تشغيل الكاميرا...");
    try {
      // Request initial stream to trigger permission check
      const initialStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      initialStream.getTracks().forEach(track => track.stop());

      // Enumerate available video inputs
      const devices = await navigator.mediaDevices.enumerateDevices();
      camerasList = devices.filter(device => device.kind === "videoinput");

      if (cameraDeviceSelect) {
        cameraDeviceSelect.innerHTML = "";
        if (camerasList.length > 1) {
          camerasList.forEach((device, index) => {
            const option = document.createElement("option");
            option.value = device.deviceId;
            option.textContent = device.label || `Camera ${index + 1} / كاميرا ${index + 1}`;
            cameraDeviceSelect.appendChild(option);
          });
          if (cameraDeviceSelectWrapper) {
            cameraDeviceSelectWrapper.hidden = false;
          }
          // Try to prefer back/rear/environment camera by default
          const rearCam = camerasList.find(c => 
            c.label.toLowerCase().includes("back") || 
            c.label.toLowerCase().includes("environment") || 
            c.label.toLowerCase().includes("rear")
          );
          currentDeviceId = rearCam ? rearCam.deviceId : camerasList[0].deviceId;
          cameraDeviceSelect.value = currentDeviceId;
        } else {
          if (cameraDeviceSelectWrapper) {
            cameraDeviceSelectWrapper.hidden = true;
          }
          currentDeviceId = camerasList.length ? camerasList[0].deviceId : null;
        }
      }

      await startStream(currentDeviceId);
      cameraModal.hidden = false;
      capturedPhotosCount = 0;
      updateCameraStatus("");
    } catch (err) {
      console.error("Camera initialization failed:", err);
      showMessage(
        "Camera Access Error / خطأ في الوصول للكاميرا",
        "Could not access the camera. Please make sure that permissions are granted and no other application is using it.\nتعذر الوصول للكاميرا. يرجى التأكد من السماح بالصلاحيات وعدم استخدامها في تطبيق آخر.",
        cameraTriggerBtn
      );
    }
  }

  function triggerShutterFlash() {
    if (!cameraFlash) return;
    cameraFlash.classList.add("flash-active");
    // Force a browser reflow/repaint to ensure transition works
    cameraFlash.offsetHeight;
    cameraFlash.classList.remove("flash-active");
  }

  function capturePhoto() {
    if (!cameraVideo || !cameraCanvas || !drugImageInput) return;

    const width = cameraVideo.videoWidth;
    const height = cameraVideo.videoHeight;
    if (!width || !height) {
      updateCameraStatus("Video feed not ready. / البث المباشر غير جاهز.", true);
      return;
    }

    cameraCanvas.width = width;
    cameraCanvas.height = height;
    const ctx = cameraCanvas.getContext("2d");
    if (!ctx) return;

    // Draw the current video frame onto the canvas
    ctx.drawImage(cameraVideo, 0, 0, width, height);

    // Apply flash effect
    triggerShutterFlash();

    // Convert canvas image to Blob
    cameraCanvas.toBlob(blob => {
      if (!blob) {
        updateCameraStatus("Failed to capture image. / فشل التقاط الصورة.", true);
        return;
      }

      // Create a native File representation
      const filename = `camera_capture_${Date.now()}.jpg`;
      const file = new File([blob], filename, { type: "image/jpeg" });

      // Add to file input files collection via DataTransfer API
      const dt = new DataTransfer();
      
      // Copy existing files
      if (drugImageInput.files) {
        Array.from(drugImageInput.files).forEach(f => dt.items.add(f));
      }
      
      // Append new file
      dt.items.add(file);
      drugImageInput.files = dt.files;

      // Dispatch 'change' event to notify existing form handlers
      const event = new Event("change", { bubbles: true });
      drugImageInput.dispatchEvent(event);

      capturedPhotosCount++;
      updateCameraStatus(`Photo captured successfully! (Total: ${capturedPhotosCount}) / تم التقاط الصورة بنجاح! (الإجمالي: ${capturedPhotosCount})`);
    }, "image/jpeg", 0.9);
  }

  // Event Listeners
  cameraTriggerBtn.addEventListener("click", initCamera);
  cameraCloseBtn?.addEventListener("click", stopCamera);
  cameraCaptureBtn?.addEventListener("click", capturePhoto);

  cameraDeviceSelect?.addEventListener("change", async (e) => {
    currentDeviceId = e.target.value;
    updateCameraStatus("Switching camera... / جاري تغيير الكاميرا...");
    try {
      await startStream(currentDeviceId);
      updateCameraStatus("");
    } catch (err) {
      console.error("Failed to switch camera:", err);
      updateCameraStatus("Failed to switch camera. / فشل تغيير الكاميرا.", true);
    }
  });

  cameraModal.addEventListener("click", (e) => {
    if (e.target === cameraModal) {
      stopCamera();
    }
  });
})();

