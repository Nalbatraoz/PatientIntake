// International Index of Erectile Function (IIEF-15) - Browser Script
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

    function buildForwardQuery(nextComplaints = complaints) {
        const nextParams = new URLSearchParams(urlParams);
        nextParams.set('complaints', nextComplaints.join(','));
        return nextParams.toString() ? `?${nextParams.toString()}` : '';
    }

    function resolveNextPage(nextComplaints = complaints) {
        if (nextComplaints.includes('low_libido')) return '/low-libido';
        if (nextComplaints.includes('premature_ejaculation')) return '/pedt';
        if (nextComplaints.includes('erectile_dysfunction')) return '/ehs';
        return '/';
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

    // Standard options sets to reuse
    const freqOptions = [
        { val: 0, en: "No sexual activity", ar: "لم يحدث نشاط جنسي" },
        { val: 1, en: "Almost never or never", ar: "تقريباً أبداً أو أبداً" },
        { val: 2, en: "A few times (less than half the time)", ar: "مرات قليلة (أقل بكثير من نصف المرات)" },
        { val: 3, en: "Sometimes (about half the time)", ar: "أحياناً (حوالي نصف المرات)" },
        { val: 4, en: "Most times (more than half the time)", ar: "معظم المرات (أكثر بكثير من نصف المرات)" },
        { val: 5, en: "Almost always or always", ar: "تقريباً دائماً أو دائماً" }
    ];

    const penetrationOptions = [
        { val: 0, en: "No sexual stimulation / Did not attempt", ar: "لم تحدث إثارة جنسية / لم أحاول الجماع" },
        { val: 1, en: "Almost never or never", ar: "تقريباً أبداً أو أبداً" },
        { val: 2, en: "A few times (less than half the time)", ar: "مرات قليلة (أقل بكثير من نصف المرات)" },
        { val: 3, en: "Sometimes (about half the time)", ar: "أحياناً (حوالي نصف المرات)" },
        { val: 4, en: "Most times (more than half the time)", ar: "معظم المرات (أكثر بكثير من نصف المرات)" },
        { val: 5, en: "Almost always or always", ar: "تقريباً دائماً أو دائماً" }
    ];

    const difficultyOptions = [
        { val: 0, en: "Did not attempt intercourse", ar: "لم أحاول الجماع" },
        { val: 1, en: "Extremely difficult", ar: "صعب للغاية" },
        { val: 2, en: "Very difficult", ar: "صعب جداً" },
        { val: 3, en: "Difficult", ar: "صعب" },
        { val: 4, en: "Slightly difficult", ar: "صعب قليلاً" },
        { val: 5, en: "Not difficult", ar: "ليس صعباً" }
    ];

    const attemptsOptions = [
        { val: 0, en: "No attempts", ar: "لا توجد محاولات" },
        { val: 1, en: "One to two attempts", ar: "محاولة واحدة إلى محاولتين" },
        { val: 2, en: "Three to four attempts", ar: "ثلاث إلى أربع محاولات" },
        { val: 3, en: "Five to six attempts", ar: "خمس إلى ست محاولات" },
        { val: 4, en: "Seven to ten attempts", ar: "سبع إلى عشر محاولات" },
        { val: 5, en: "Eleven or more attempts", ar: "إحدى عشرة محاولة أو أكثر" }
    ];

    const enjoymentOptions = [
        { val: 0, en: "No intercourse", ar: "لم يحدث جماع" },
        { val: 1, en: "No enjoyment at all", ar: "لا يوجد أي استمتاع على الإطلاق" },
        { val: 2, en: "Not very enjoyable", ar: "غير ممتع كثيراً" },
        { val: 3, en: "Fairly enjoyable", ar: "ممتع بدرجة مقبولة" },
        { val: 4, en: "Highly enjoyable", ar: "ممتع للغاية" },
        { val: 5, en: "Very highly enjoyable", ar: "ممتع جداً جداً" }
    ];

    const desireFreqOptions = [
        { val: 1, en: "Almost never or never", ar: "تقريباً أبداً أو أبداً" },
        { val: 2, en: "A few times (less than half the time)", ar: "مرات قليلة (أقل بكثير من نصف المرات)" },
        { val: 3, en: "Sometimes (about half the time)", ar: "أحياناً (حوالي نصف المرات)" },
        { val: 4, en: "Most times (more than half the time)", ar: "معظم المرات (أكثر بكثير من نصف المرات)" },
        { val: 5, en: "Almost always or always", ar: "تقريباً دائماً أو دائماً" }
    ];

    const desireLevelOptions = [
        { val: 1, en: "Very low or none at all", ar: "منخفض جداً أو لا يوجد على الإطلاق" },
        { val: 2, en: "Low", ar: "منخفض" },
        { val: 3, en: "Moderate", ar: "متوسط" },
        { val: 4, en: "High", ar: "مرتفع" },
        { val: 5, en: "Very high", ar: "مرتفع جداً" }
    ];

    const satisfactionOptions = [
        { val: 1, en: "Very dissatisfied", ar: "غير راضٍ تماماً" },
        { val: 2, en: "Moderately dissatisfied", ar: "غير راضٍ بدرجة متوسطة" },
        { val: 3, en: "About equally satisfied and dissatisfied", ar: "متساوي الرضا وعدم الرضا" },
        { val: 4, en: "Moderately satisfied", ar: "راضٍ بدرجة متوسطة" },
        { val: 5, en: "Very satisfied", ar: "راضٍ تماماً" }
    ];

    const confidenceOptions = [
        { val: 1, en: "Very low", ar: "منخفضة جداً" },
        { val: 2, en: "Low", ar: "منخفضة" },
        { val: 3, en: "Moderate", ar: "متوسطة" },
        { val: 4, en: "High", ar: "مرتفعة" },
        { val: 5, en: "Very high", ar: "مرتفعة جداً" }
    ];

    const questions = [
        {
            id: 1,
            domain: "ef",
            textEn: "How often were you able to get an erection during sexual activity?",
            textAr: "كم مرة تمكنت من الحصول على انتصاب أثناء النشاط الجنسي؟",
            options: freqOptions
        },
        {
            id: 2,
            domain: "ef",
            textEn: "When you had erections with sexual stimulation, how often were your erections hard enough for penetration?",
            textAr: "عندما حصلت على انتصاب مع الإثارة الجنسية، كم مرة كان الانتصاب صلباً بما يكفي للإيلاج؟",
            options: penetrationOptions
        },
        {
            id: 3,
            domain: "ef",
            textEn: "When you attempted sexual intercourse, how often were you able to penetrate (enter) your partner?",
            textAr: "عندما حاولت الجماع، كم مرة تمكنت من إيلاج العضو لدى شريكتك؟",
            options: penetrationOptions
        },
        {
            id: 4,
            domain: "ef",
            textEn: "During sexual intercourse, how often were you able to maintain your erection after you had penetrated (entered) your partner?",
            textAr: "أثناء الجماع، كم مرة تمكنت من الحفاظ على الانتصاب بعد إيلاج العضو لدى شريكتك؟",
            options: penetrationOptions
        },
        {
            id: 5,
            domain: "ef",
            textEn: "During sexual intercourse, how difficult was it to maintain your erection to completion of intercourse?",
            textAr: "أثناء الجماع، كم كانت درجة الصعوبة في الحفاظ على الانتصاب حتى إتمام العملية الجنسية؟",
            options: difficultyOptions
        },
        {
            id: 6,
            domain: "is",
            textEn: "How many times have you attempted sexual intercourse?",
            textAr: "كم عدد المرات التي حاولت فيها الجماع؟",
            options: attemptsOptions
        },
        {
            id: 7,
            domain: "is",
            textEn: "When you attempted sexual intercourse, how often was it satisfactory for you?",
            textAr: "عندما حاولت الجماع، كم مرة كان الأمر مرضياً وممتعاً بالنسبة لك؟",
            options: penetrationOptions
        },
        {
            id: 8,
            domain: "is",
            textEn: "How much have you enjoyed sexual intercourse?",
            textAr: "ما هي درجة استمتاعك بالجماع؟",
            options: enjoymentOptions
        },
        {
            id: 9,
            domain: "of",
            textEn: "When you had sexual stimulation or intercourse, how often did you ejaculate?",
            textAr: "عندما كان لديك إثارة جنسية أو جماع، كم مرة قذفت؟",
            options: freqOptions
        },
        {
            id: 10,
            domain: "of",
            textEn: "When you had sexual stimulation or intercourse, how often did you have the feeling of orgasm or climax?",
            textAr: "عندما كان لديك إثارة جنسية أو جماع، كم مرة شعرت بالرعشة الجنسية (النشوة)؟",
            options: freqOptions
        },
        {
            id: 11,
            domain: "sd",
            textEn: "How often have you felt sexual desire?",
            textAr: "كم مرة شعرت بالرغبة الجنسية؟",
            options: desireFreqOptions
        },
        {
            id: 12,
            domain: "sd",
            textEn: "How would you rate your level of sexual desire?",
            textAr: "كيف تقيم مستوى رغبتك الجنسية؟",
            options: desireLevelOptions
        },
        {
            id: 13,
            domain: "os",
            textEn: "How satisfied have you been with your overall sex life?",
            textAr: "ما مدى رضاك عن حياتك الجنسية بشكل عام؟",
            options: satisfactionOptions
        },
        {
            id: 14,
            domain: "os",
            textEn: "How satisfied have you been with your sexual relationship with your partner?",
            textAr: "ما مدى رضاك عن علاقتك الجنسية مع شريكتك؟",
            options: satisfactionOptions
        },
        {
            id: 15,
            domain: "ef",
            textEn: "How do you rate your confidence that you could get and keep an erection?",
            textAr: "كيف تقيم مستوى ثقتك في قدرتك على الحصول على انتصاب والحفاظ عليه؟",
            options: confidenceOptions
        }
    ];

    const group1Container = document.getElementById("questions-group-1");
    const group2Container = document.getElementById("questions-group-2");

    // Dynamic question rendering matching layout of documents
    questions.forEach(q => {
        const div = document.createElement("div");
        div.className = "question-row";
        div.id = `q-row-${q.id}`;

        // Shading logic: Odd Qs on page 2 (Q1,3,5) and Even Qs on page 3 (Q6,8,10,12,14) are shaded
        const isShaded = (q.id <= 5 && q.id % 2 !== 0) || (q.id > 5 && q.id % 2 === 0);
        if (isShaded) {
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

        if (q.id <= 5) {
            group1Container.appendChild(div);
        } else {
            group2Container.appendChild(div);
        }
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

    // Step Stepper Navigation Logic
    let currentStep = 1;

    function showStep(stepNum) {
        document.querySelectorAll(".step-container").forEach(el => {
            el.classList.add("hidden");
        });
        const currentContainer = document.getElementById(`step-${stepNum}`);
        if (currentContainer) {
            currentContainer.classList.remove("hidden");
            // Scroll to the top of the form cleanly
            currentContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        currentStep = stepNum;
    }

    // Validation per step
    function validateStep(step) {
        let unanswered = [];
        const targetQuestions = (step === 2) ? [1, 2, 3, 4, 5] : [6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
        
        targetQuestions.forEach(id => {
            const checked = document.querySelector(`input[name="q${id}"]:checked`);
            if (!checked) {
                unanswered.push(id);
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

    document.getElementById("toStep3").addEventListener("click", () => {
        const unanswered = validateStep(2);
        if (unanswered.length > 0) {
            highlightUnanswered(unanswered);
            alert("Please answer all questions Q1 - Q5 before proceeding.\nيرجى الإجابة على جميع الأسئلة Q1 - Q5 للمتابعة.");
        } else {
            showStep(3);
        }
    });

    document.getElementById("backToStep2").addEventListener("click", () => {
        showStep(2);
    });

    // Handle questionnaire submission
    document.getElementById("iiefForm").addEventListener("submit", async function(e) {
        e.preventDefault();

        // Validate step 3 questions
        const unanswered = validateStep(3);
        if (unanswered.length > 0) {
            highlightUnanswered(unanswered);
            alert("Please answer all questions Q6 - Q15 before submitting.\nيرجى الإجابة على جميع الأسئلة Q6 - Q15 للإرسال.");
            return;
        }

        const submitBtn = document.getElementById("iiefSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting answers... / جاري الإرسال...";

        let total = 0;
        let domainScores = { ef: 0, of: 0, sd: 0, is: 0, os: 0 };
        const answers = {};

        questions.forEach(q => {
            const checkedRadio = document.querySelector(`input[name="q${q.id}"]:checked`);
            if (checkedRadio) {
                const val = parseInt(checkedRadio.value, 10);
                answers[`q${q.id}`] = val;
                total += val;
                domainScores[q.domain] += val;
            }
        });

        // Graded Severity of ED based on Erectile Function domain score (out of 30)
        let severityEn = "";
        let severityAr = "";
        let severityClass = "";
        const ef = domainScores.ef;

        if (ef >= 26) {
            severityEn = "No Erectile Dysfunction";
            severityAr = "لا يوجد ضعف انتصاب";
            severityClass = "severity-none";
        } else if (ef >= 22) {
            severityEn = "Mild Erectile Dysfunction";
            severityAr = "ضعف انتصاب بسيط";
            severityClass = "severity-mild";
        } else if (ef >= 17) {
            severityEn = "Mild to Moderate Erectile Dysfunction";
            severityAr = "ضعف انتصاب بسيط إلى متوسط";
            severityClass = "severity-mild-mod";
        } else if (ef >= 11) {
            severityEn = "Moderate Erectile Dysfunction";
            severityAr = "ضعف انتصاب متوسط";
            severityClass = "severity-moderate";
        } else {
            severityEn = "Severe Erectile Dysfunction";
            severityAr = "ضعف انتصاب شديد";
            severityClass = "severity-severe";
        }

        const iief_data = {
            answers: answers,
            scores: {
                total: total,
                ef: domainScores.ef,
                of: domainScores.of,
                sd: domainScores.sd,
                is: domainScores.is,
                os: domainScores.os
            },
            severity: {
                en: severityEn,
                ar: severityAr,
                cssClass: severityClass
            }
        };

        try {
            const response = await fetch("/submit-iief", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: submissionId || 0,
                    iief_data: iief_data
                })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Submission failed.");

            // Success: Hide form elements (including navigation blocks)
            document.getElementById("step-1").style.display = "none";
            document.getElementById("step-2").style.display = "none";
            document.getElementById("step-3").style.display = "none";
            
            const resultsDiv = document.getElementById("results");
            resultsDiv.classList.remove("hidden");

            // Setup the continue button link to forward metadata to PEDT Questionnaire page
            const continueBtn = document.getElementById("continueBtn");
            if (continueBtn) {
                const nextPage = resolveNextPage();
                continueBtn.href = `${nextPage}${nextPage === '/' ? '' : buildForwardQuery()}`;
                continueBtn.textContent = nextPage === '/'
                    ? 'Finish / إنهاء'
                    : 'Continue / متابعة →';
            }

            // Scroll to results top smoothly
            resultsDiv.scrollIntoView({ behavior: "smooth", block: "start" });

        } catch (error) {
            console.error("IIEF Submit error:", error);
            alert("Error submitting questionnaire: " + error.message + "\nPlease try again.");
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit Questionnaire / إرسال الاستبيان";
        }
    });
})();
