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
    const fullName = urlParams.get("fullName");
    const dob = urlParams.get("dob");
    const age = urlParams.get("age");
    const phone = urlParams.get("phone");
    const address = urlParams.get("address");
    const complaints = (urlParams.get("complaints") || "")
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);

    if (!complaints.includes("erectile_dysfunction")) {
        window.location.replace("/");
        return;
    }

    const nameInput = document.querySelector('[name="name"]');
    const dobInput = document.querySelector('[name="dob"]');
    const ageInput = document.querySelector('[name="age"]');
    const phoneInput = document.querySelector('[name="phone"]');
    const addressInput = document.querySelector('[name="address"]');

    if (fullName && nameInput) nameInput.value = fullName;
    if (dob && dobInput) dobInput.value = dob;
    if (age && ageInput) ageInput.value = age;
    if (phone && phoneInput) phoneInput.value = phone;
    if (address && addressInput) addressInput.value = address;

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
            const response = await fetch("/submit-ehs", {
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

            document.getElementById("withoutScore").textContent = `${withoutIntervention} / 4`;
            document.getElementById("withScore").textContent = `${withIntervention} / 4`;
            const badge = document.getElementById("assessment");
            badge.textContent = `${severityEn} / ${severityAr}`;
            badge.className = `severity-badge ${severityClass}`;

            const continueBtn = document.getElementById("continueBtn");
            if (continueBtn) {
                continueBtn.href = "/";
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
