// Premature Ejaculation Diagnostic Tool (PEDT) - Redesigned Browser Script
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get('submission_id');
    const fullName = urlParams.get('fullName');
    const dob = urlParams.get('dob');
    const age = urlParams.get('age');
    const phone = urlParams.get('phone');
    const address = urlParams.get('address');
    const complaints = (urlParams.get('complaints') || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    function buildForwardQuery(updatedComplaints) {
        const nextParams = new URLSearchParams(urlParams);
        nextParams.set('complaints', updatedComplaints.join(','));
        return nextParams.toString() ? `?${nextParams.toString()}` : '';
    }

    function resolveNextPage(updatedComplaints) {
        if (updatedComplaints.includes('erectile_dysfunction')) return '/ehs';
        return '/';
    }

    if (!complaints.includes('premature_ejaculation')) {
        const nextPage = resolveNextPage(complaints);
        if (nextPage !== window.location.pathname) {
            window.location.replace(`${nextPage}${nextPage === '/' ? '' : buildForwardQuery(complaints)}`);
        }
        return;
    }

    // Pre-fill patient details if available from query parameters
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

    // Standard options sets
    const difficultyOptions = [
        { val: 0, en: "Not difficult at all", ar: "ليس صعباً على الإطلاق" },
        { val: 1, en: "Somewhat difficult", ar: "صعب نوعاً ما" },
        { val: 2, en: "Moderately difficult", ar: "صعب بدرجة متوسطة" },
        { val: 3, en: "Very difficult", ar: "صعب جداً" },
        { val: 4, en: "Extremely difficult", ar: "صعب للغاية" }
    ];

    const freqOptions = [
        { val: 0, en: "Never or almost never (0%)", ar: "أبداً أو شبه أبداً (0%)" },
        { val: 1, en: "Less than half the time (25%)", ar: "أقل من نصف المرات (25%)" },
        { val: 2, en: "About half the time (50%)", ar: "حوالي نصف المرات (50%)" },
        { val: 3, en: "Over half the time (75%)", ar: "أكثر من نصف المرات (75%)" },
        { val: 4, en: "Always or almost always (100%)", ar: "دائماً أو شبه دائماً (100%)" }
    ];

    const concernOptions = [
        { val: 0, en: "Not at all", ar: "لا أشعر بذلك على الإطلاق" },
        { val: 1, en: "Slightly", ar: "قليلاً" },
        { val: 2, en: "Moderately", ar: "بدرجة متوسطة" },
        { val: 3, en: "Very", ar: "جداً" },
        { val: 4, en: "Extremely", ar: "للغاية" }
    ];

    const questions = [
        {
            id: 1,
            textEn: "How difficult is it for you to delay ejaculation?",
            textAr: "ما مدى صعوبة تأخير القذف بالنسبة لك؟",
            options: difficultyOptions
        },
        {
            id: 2,
            textEn: "Do you ejaculate before you want to?",
            textAr: "هل تقذف قبل أن ترغب في ذلك؟",
            options: freqOptions
        },
        {
            id: 3,
            textEn: "Do you ejaculate with very little stimulation?",
            textAr: "هل تقذف مع إثارة بسيطة جداً؟",
            options: freqOptions
        },
        {
            id: 4,
            textEn: "Do you feel frustrated because of ejaculating before you want to?",
            textAr: "هل تشعر بالإحباط بسبب القذف قبل أن ترغب في ذلك؟",
            options: concernOptions
        },
        {
            id: 5,
            textEn: "How concerned are you that your time to ejaculation leaves your partner unfulfilled?",
            textAr: "ما مدى قلقك من أن وقت القذف لديك يترك شريكتك غير راضية؟",
            options: concernOptions
        }
    ];

    const container = document.getElementById("questions");

    // Dynamic question rendering
    questions.forEach(q => {
        const div = document.createElement("div");
        div.className = "question-row";
        div.id = `q-row-${q.id}`;

        // Alternating shading styling for odd questions (Q1, 3, 5)
        if (q.id % 2 !== 0) {
            div.classList.add("shaded");
        }

        let optionsHtml = "";
        q.options.forEach(opt => {
            optionsHtml += `
            <label class="option-item">
                <input
                    type="radio"
                    name="q${q.id}"
                    value="${opt.val}"
                    required
                >
                <span class="option-number">${opt.val}</span>
                <span class="option-label-text">
                    <span class="opt-en">${opt.en}</span>
                    <span class="opt-ar" dir="rtl">${opt.ar}</span>
                </span>
            </label>
            `;
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
                <div class="options-vertical">
                    ${optionsHtml}
                </div>
            </div>
        `;

        container.appendChild(div);
    });

    // Update scorer box and styling on selection
    document.addEventListener("change", function(e) {
        if (e.target.name && e.target.name.startsWith("q")) {
            const qId = e.target.name.substring(1);
            const val = e.target.value;
            const scorerBox = document.getElementById(`scorer-q${qId}`);
            if (scorerBox) {
                scorerBox.textContent = val;
                scorerBox.classList.add("filled");
            }
            // Clear error highlight on selection
            const row = document.getElementById(`q-row-${qId}`);
            if (row) {
                row.classList.remove("error-highlight");
            }
        }
    });

    // Stepper Navigation Logic
    let currentStep = 1;

    function showStep(stepNum) {
        document.querySelectorAll(".step-container").forEach(el => {
            el.classList.add("hidden");
        });
        const currentContainer = document.getElementById(`step-${stepNum}`);
        if (currentContainer) {
            currentContainer.classList.remove("hidden");
            // Scroll to the top of the container smoothly
            currentContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        currentStep = stepNum;
    }

    // Step validation helper
    function validateForm() {
        let unanswered = [];
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
        
        // Scroll to the first unanswered question
        if (ids.length > 0) {
            const firstRow = document.getElementById(`q-row-${ids[0]}`);
            if (firstRow) {
                firstRow.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }

    // Navigation buttons event listeners
    document.getElementById("startBtn").addEventListener("click", () => {
        showStep(2);
    });

    document.getElementById("backToStep1").addEventListener("click", () => {
        showStep(1);
    });

    // Handle questionnaire submission
    document.getElementById("pedtForm").addEventListener("submit", async function(e) {
        e.preventDefault();

        // Validate all 5 questions
        const unanswered = validateForm();
        if (unanswered.length > 0) {
            highlightUnanswered(unanswered);
            alert("Please answer all questions Q1 - Q5 before submitting.\nيرجى الإجابة على جميع الأسئلة Q1 - Q5 للإرسال.");
            return;
        }

        const submitBtn = document.getElementById("pedtSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting answers... / جاري الإرسال...";

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

        // Graded Severity of PE based on total score (out of 20)
        let severityEn = "";
        let severityAr = "";
        let severityClass = "";

        if (total <= 8) {
            severityEn = "Low likelihood of PE";
            severityAr = "احتمالية منخفضة لسرعة القذف";
            severityClass = "severity-none";
        } else if (total <= 10) {
            severityEn = "Possible PE";
            severityAr = "احتمالية وجود سرعة قذف";
            severityClass = "severity-moderate";
        } else {
            severityEn = "Probable PE";
            severityAr = "احتمالية عالية لسرعة القذف";
            severityClass = "severity-severe";
        }

        const pedt_data = {
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
            const response = await fetch("/submit-pedt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: submissionId || 0,
                    pedt_data: pedt_data
                })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Submission failed.");

            // Success: Hide form elements
            document.getElementById("step-1").style.display = "none";
            document.getElementById("step-2").style.display = "none";
            
            const resultsDiv = document.getElementById("results");
            resultsDiv.classList.remove("hidden");

            document.getElementById("totalScore").textContent = `${total} / 20`;
            
            const badge = document.getElementById("assessment");
            badge.textContent = `${severityEn} / ${severityAr}`;
            badge.className = `severity-badge ${severityClass}`;

            const remainingComplaints = complaints.filter(item => item !== 'premature_ejaculation');
            const continueBtn = document.getElementById("continueBtn");
            if (continueBtn) {
                const nextPage = resolveNextPage(remainingComplaints);
                continueBtn.href = `${nextPage}${nextPage === '/' ? '' : buildForwardQuery(remainingComplaints)}`;
                continueBtn.textContent = nextPage === '/'
                    ? 'Finish / إنهاء'
                    : 'Continue / متابعة →';
            }

            // Scroll to results top smoothly
            resultsDiv.scrollIntoView({ behavior: "smooth", block: "start" });

        } catch (error) {
            console.error("PEDT Submit error:", error);
            alert("Error submitting questionnaire: " + error.message + "\nPlease try again.");
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit Questionnaire / إرسال الاستبيان";
        }
    });
})();
