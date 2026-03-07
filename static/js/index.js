/* UX enhancements for patient intake workflow with animated slider controls */
(function () {
  const form = document.getElementById("patientForm");
  if (!form) return;

  const ageField = document.getElementById("ageField");
  const bpField = document.getElementById("bpField");
  const cholField = document.getElementById("cholField");
  const ageBadge = document.getElementById("ageValueBadge");
  const bpBadge = document.getElementById("bpValueBadge");
  const cholBadge = document.getElementById("cholValueBadge");
  const readiness = document.getElementById("readinessState");
  const submitBtn = document.getElementById("predictBtn");

  if (!ageField || !bpField || !cholField || !readiness || !submitBtn) return;

  function inRange(value, min, max) {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= min && parsed <= max;
  }

  function animateBadge(badge, text) {
    if (!badge) return;
    badge.textContent = text;
    badge.classList.remove("is-updating");
    requestAnimationFrame(() => badge.classList.add("is-updating"));
  }

  function updateSliderFill(slider) {
    const min = Number(slider.min || 0);
    const max = Number(slider.max || 100);
    const value = Number(slider.value || 0);
    const percent = ((value - min) / Math.max(1, max - min)) * 100;
    slider.style.setProperty("--slider-fill", `${Math.max(0, Math.min(100, percent))}%`);
  }

  function updateSliderUi() {
    animateBadge(ageBadge, `${ageField.value} years`);
    animateBadge(bpBadge, `${bpField.value} mmHg`);
    animateBadge(cholBadge, `${cholField.value} mg/dL`);

    updateSliderFill(ageField);
    updateSliderFill(bpField);
    updateSliderFill(cholField);
  }

  function updateReadiness() {
    const ageOk = inRange(ageField.value, 1, 120);
    const bpOk = inRange(bpField.value, 50, 260);
    const cholOk = inRange(cholField.value, 80, 500);

    readiness.classList.remove("is-ready", "is-pending");
    if (ageOk && bpOk && cholOk) {
      readiness.textContent = "Input complete. Ready for analysis.";
      readiness.classList.add("is-ready");
      return;
    }

    if (ageField.value || bpField.value || cholField.value) {
      readiness.textContent = "Input partially complete.";
      readiness.classList.add("is-pending");
      return;
    }

    readiness.textContent = "Waiting for complete inputs";
  }

  function refreshFormState() {
    updateSliderUi();
    updateReadiness();
  }

  document.querySelectorAll(".js-profile-fill").forEach((button) => {
    button.addEventListener("click", () => {
      ageField.value = button.dataset.age || ageField.value;
      bpField.value = button.dataset.bp || bpField.value;
      cholField.value = button.dataset.chol || cholField.value;
      refreshFormState();
    });
  });

  [ageField, bpField, cholField].forEach((field) => {
    field.addEventListener("input", refreshFormState);
    field.addEventListener("change", refreshFormState);
  });

  form.addEventListener("submit", () => {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Analyzing Patient Data...';
  });

  refreshFormState();
})();
