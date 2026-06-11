// Low Libido Assessment Questionnaire - Browser Script
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
        if (updatedComplaints.includes('premature_ejaculation')) return '/pedt';
        if (updatedComplaints.includes('erectile_dysfunction')) return '/ehs';
        return '/';
    }

    if (!complaints.includes('low_libido')) {
        const nextPage = resolveNextPage(complaints);
        if (nextPage !== window.location.pathname) {
            window.location.replace(`${nextPage}${nextPage === '/' ? '' : buildForwardQuery(complaints)}`);
        }
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
            const response = await fetch("/submit-low-libido", {
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

            const resultsDiv = document.getElementById("results");
            resultsDiv.classList.remove("hidden");
            document.getElementById("totalScore").textContent = `${total} / 40`;

            const badge = document.getElementById("assessment");
            badge.textContent = `${severityEn} / ${severityAr}`;
            badge.className = `severity-badge ${severityClass}`;

            const remainingComplaints = complaints.filter(item => item !== 'low_libido');
            const continueBtn = document.getElementById("continueBtn");
            if (continueBtn) {
                const nextPage = resolveNextPage(remainingComplaints);
                continueBtn.href = `${nextPage}${nextPage === '/' ? '' : buildForwardQuery(remainingComplaints)}`;
                continueBtn.textContent = nextPage === '/'
                    ? 'Finish / إنهاء'
                    : 'Continue / متابعة →';
            }

            resultsDiv.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (error) {
            console.error("Low Libido Submit error:", error);
            alert("Error submitting questionnaire: " + error.message + "\nPlease try again.");
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit Questionnaire / إرسال الاستبيان";
        }
    });
})();
