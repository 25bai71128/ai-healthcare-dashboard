/* Dashboard UX enhancements: lazy charts, what-if simulation, model admin, history, and clinician notes */
(function () {
  const payload = window.__RESULT_PAYLOAD__;
  if (!payload) return;

  const historyRecords = window.__HISTORY_RECORDS__ || [];
  const modelCatalog = window.__MODEL_CATALOG__ || {};
  const prefersReducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function updateSliderFill(slider) {
    if (!slider) return;
    const min = Number(slider.min || 0);
    const max = Number(slider.max || 100);
    const value = Number(slider.value || 0);
    const pct = clamp(((value - min) / Math.max(1, max - min)) * 100, 0, 100);
    slider.style.setProperty("--slider-fill", `${pct}%`);
  }

  const progress = document.getElementById("healthProgress");
  if (progress) {
    const width = Number(progress.dataset.width || 0);
    requestAnimationFrame(() => {
      progress.style.width = clamp(width, 0, 100) + "%";
    });
  }

  const gauge = document.getElementById("healthGauge");
  if (gauge) {
    const score = Number(gauge.dataset.score || 0);
    const safeScore = clamp(score, 0, 100);
    gauge.style.background = `conic-gradient(#2563eb ${safeScore}%, #e5e7eb ${safeScore}% 100%)`;
  }

  document.querySelectorAll(".js-impact-bar").forEach((bar, index) => {
    const impact = Number(bar.dataset.impact || 0);
    setTimeout(() => {
      bar.style.width = clamp(impact, 0, 100) + "%";
    }, 100 + index * 40);
  });

  const requestButton = document.getElementById("copyRequestId");
  if (requestButton) {
    requestButton.addEventListener("click", async () => {
      const value = requestButton.dataset.requestId || "";
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        requestButton.innerHTML = '<i class="fa-solid fa-check me-1"></i>Copied';
        setTimeout(() => {
          requestButton.innerHTML = '<i class="fa-regular fa-copy me-1"></i>Copy Request ID';
        }, 1200);
      } catch (_error) {
        requestButton.innerHTML = '<i class="fa-solid fa-xmark me-1"></i>Copy failed';
      }
    });
  }

  // Keyboard shortcuts for workflow speed.
  document.addEventListener("keydown", (event) => {
    const tag = (event.target && event.target.tagName || "").toLowerCase();
    const isTyping = tag === "input" || tag === "textarea" || event.target.isContentEditable;
    if (isTyping) return;

    if (event.key.toLowerCase() === "w") {
      const simAge = document.getElementById("simAge");
      if (simAge) simAge.focus();
    }

    if (event.key.toLowerCase() === "n") {
      const noteBox = document.getElementById("caseNote");
      if (noteBox) noteBox.focus();
    }
  });

  const cardsContainer = document.getElementById("modelCards");
  const sortSelect = document.getElementById("modelSort");
  const highRiskToggle = document.getElementById("highRiskOnly");

  function sortAndFilterCards() {
    if (!cardsContainer) return;
    const cards = Array.from(cardsContainer.querySelectorAll(".js-model-card"));
    const sortMode = sortSelect ? sortSelect.value : "risk_desc";
    const highRiskOnly = highRiskToggle ? highRiskToggle.checked : false;

    cards.sort((a, b) => {
      const riskA = Number(a.dataset.risk || 0);
      const riskB = Number(b.dataset.risk || 0);
      const nameA = a.dataset.name || "";
      const nameB = b.dataset.name || "";
      if (sortMode === "risk_asc") return riskA - riskB;
      if (sortMode === "name_asc") return nameA.localeCompare(nameB);
      return riskB - riskA;
    });

    cards.forEach((card) => {
      const level = (card.dataset.level || "").toLowerCase();
      const shouldHide = highRiskOnly && level === "low";
      card.classList.toggle("d-none", shouldHide);
      cardsContainer.appendChild(card);
    });
  }

  if (sortSelect) sortSelect.addEventListener("change", sortAndFilterCards);
  if (highRiskToggle) highRiskToggle.addEventListener("change", sortAndFilterCards);
  sortAndFilterCards();

  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: prefersReducedMotion ? 0 : 650,
      easing: "easeOutQuart",
    },
    plugins: {
      legend: {
        labels: {
          font: { family: "Source Sans 3" },
        },
      },
    },
  };

  const createdCharts = {};

  function createIndicatorChart() {
    const canvas = document.getElementById("indicatorChart");
    if (!canvas || createdCharts.indicator) return;
    createdCharts.indicator = new Chart(canvas, {
      type: "bar",
      data: {
        labels: ["Age", "Blood Pressure", "Cholesterol"],
        datasets: [{
          label: "Patient Indicators",
          data: [payload.patient_data.age, payload.patient_data.blood_pressure, payload.patient_data.cholesterol],
          backgroundColor: ["#2563eb", "#10b981", "#f59e0b"],
          borderRadius: 8,
        }],
      },
      options: {
        ...chartDefaults,
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  function createComparisonChart() {
    const canvas = document.getElementById("comparisonChart");
    if (!canvas || createdCharts.comparison) return;
    const items = Object.values(payload.model_predictions || {});
    const names = items.map((item) => `${item.metadata.model_name} v${item.version}`);
    const risks = items.map((item) => item.risk_percent);

    createdCharts.comparison = new Chart(canvas, {
      type: "bar",
      data: {
        labels: names,
        datasets: [{
          label: "Risk Probability (%)",
          data: risks,
          backgroundColor: "rgba(37, 99, 235, 0.85)",
          borderColor: "#1d4ed8",
          borderWidth: 1,
          borderRadius: 6,
        }],
      },
      options: {
        ...chartDefaults,
        scales: { y: { min: 0, max: 100 } },
      },
    });
  }

  function createBreakdownChart() {
    const canvas = document.getElementById("riskBreakdownChart");
    if (!canvas || createdCharts.breakdown) return;

    createdCharts.breakdown = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Health Risk", "Healthy Margin"],
        datasets: [{
          data: [payload.health_score.overall_health_score, 100 - payload.health_score.overall_health_score],
          backgroundColor: ["#ef4444", "#10b981"],
          borderWidth: 0,
        }],
      },
      options: {
        ...chartDefaults,
        cutout: "68%",
      },
    });
  }

  function createHistoryChart() {
    const canvas = document.getElementById("historyChart");
    if (!canvas || createdCharts.history) return;

    const rows = [...historyRecords].reverse();
    const labels = rows.map((row) => String(row.created_at || "").replace("T", " ").slice(0, 16));
    const values = rows.map((row) => Number((row.health_score || {}).overall_health_score || 0));

    createdCharts.history = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Health Score Trend",
          data: values,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37,99,235,0.15)",
          pointRadius: 3,
          tension: 0.25,
          fill: true,
        }],
      },
      options: {
        ...chartDefaults,
        scales: { y: { min: 0, max: 100 } },
      },
    });
  }

  function createFeatureImpactChart() {
    const canvas = document.getElementById("featureImpactChart");
    if (!canvas || createdCharts.featureImpact) return;

    let impacts = Array.isArray(payload.feature_impacts) ? payload.feature_impacts : [];
    if (!impacts.length) {
      const fallback = {};
      Object.values(payload.model_predictions || {}).forEach((entry) => {
        (entry.top_features || []).forEach((feature) => {
          const key = feature.feature || "unknown";
          fallback[key] = (fallback[key] || 0) + Number(feature.impact_percent || 0);
        });
      });
      impacts = Object.entries(fallback)
        .map(([feature, impact]) => ({ feature, impact_percent: impact, label: feature.replaceAll("_", " ") }))
        .sort((a, b) => b.impact_percent - a.impact_percent);
    }

    const top = impacts.slice(0, 6);
    const labels = top.map((item) => item.label || item.feature || "Feature");
    const values = top.map((item) => Number(item.impact_percent || 0));

    createdCharts.featureImpact = new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Cumulative Impact %",
          data: values,
          backgroundColor: ["#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"],
          borderRadius: 6,
        }],
      },
      options: {
        ...chartDefaults,
        indexAxis: "y",
        scales: { x: { min: 0, max: 100 } },
      },
    });
  }

  function createWeightRiskChart() {
    const canvas = document.getElementById("weightRiskChart");
    if (!canvas || createdCharts.weightRisk) return;

    const items = Object.values(payload.model_predictions || {});
    const points = items.map((item) => ({
      x: Number(item.weight || 0),
      y: Number(item.risk_percent || 0),
      label: item.metadata.model_name || "Model",
    }));

    createdCharts.weightRisk = new Chart(canvas, {
      type: "bubble",
      data: {
        datasets: [{
          label: "Model Weight vs Risk",
          data: points.map((point) => ({ x: point.x, y: point.y, r: Math.max(8, point.x * 26) })),
          backgroundColor: "rgba(37, 99, 235, 0.45)",
          borderColor: "#1d4ed8",
        }],
      },
      options: {
        ...chartDefaults,
        scales: {
          x: { title: { display: true, text: "Model Weight" }, min: 0, max: 1 },
          y: { title: { display: true, text: "Risk %" }, min: 0, max: 100 },
        },
        plugins: {
          ...chartDefaults.plugins,
          tooltip: {
            callbacks: {
              label(context) {
                const item = points[context.dataIndex] || { label: "Model", x: 0, y: 0 };
                return `${item.label}: weight ${item.x}, risk ${item.y}%`;
              },
            },
          },
        },
      },
    });
  }

  const chartFactory = {
    indicator: createIndicatorChart,
    comparison: createComparisonChart,
    breakdown: createBreakdownChart,
    history: createHistoryChart,
    featureImpact: createFeatureImpactChart,
    weightRisk: createWeightRiskChart,
  };

  // Lazy render charts when canvases enter viewport.
  const lazyCharts = Array.from(document.querySelectorAll(".js-lazy-chart"));
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const chartName = entry.target.dataset.chart;
        if (chartFactory[chartName]) {
          chartFactory[chartName]();
        }
        obs.unobserve(entry.target);
      });
    }, { rootMargin: "120px" });

    lazyCharts.forEach((item) => observer.observe(item));
  } else {
    Object.values(chartFactory).forEach((fn) => fn());
  }

  // What-if simulator.
  const simAge = document.getElementById("simAge");
  const simBp = document.getElementById("simBp");
  const simChol = document.getElementById("simChol");
  const simAgeValue = document.getElementById("simAgeValue");
  const simBpValue = document.getElementById("simBpValue");
  const simCholValue = document.getElementById("simCholValue");
  const simState = document.getElementById("simulatorState");
  const simScore = document.getElementById("simScore");
  const simRisk = document.getElementById("simRisk");

  function updateSimLabel() {
    if (simAgeValue) simAgeValue.textContent = `${simAge.value} years`;
    if (simBpValue) simBpValue.textContent = `${simBp.value} mmHg`;
    if (simCholValue) simCholValue.textContent = `${simChol.value} mg/dL`;
    updateSliderFill(simAge);
    updateSliderFill(simBp);
    updateSliderFill(simChol);
  }

  let whatIfTimer = null;
  async function runWhatIf() {
    if (!simAge || !simBp || !simChol) return;
    if (simState) simState.textContent = "Running live simulation...";

    try {
      const response = await fetch("/api/whatif", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: Number(simAge.value),
          blood_pressure: Number(simBp.value),
          cholesterol: Number(simChol.value),
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error((data.error && data.error.message) || "Simulation failed");
      }

      const score = data.data.health_score.overall_health_score;
      const level = data.data.health_score.risk_level;
      if (simScore) simScore.textContent = `${score}%`;
      if (simRisk) simRisk.textContent = `${level} risk (${data.data.health_score.model_count} model(s))`;
      if (simState) simState.textContent = "Simulation updated (not persisted).";
    } catch (error) {
      if (simState) simState.textContent = "Simulation unavailable right now.";
      if (simRisk) simRisk.textContent = String(error.message || "Request failed");
    }
  }

  function scheduleWhatIf() {
    updateSimLabel();
    clearTimeout(whatIfTimer);
    whatIfTimer = setTimeout(runWhatIf, 220);
  }

  [simAge, simBp, simChol].forEach((slider) => {
    if (!slider) return;
    slider.addEventListener("input", scheduleWhatIf);
  });

  updateSimLabel();
  runWhatIf();

  // Model admin panel.
  const familySelect = document.getElementById("familySelect");
  const versionSelect = document.getElementById("versionSelect");
  const activateBtn = document.getElementById("activateVersionBtn");
  const refreshCatalogBtn = document.getElementById("refreshCatalogBtn");
  const adminStatus = document.getElementById("adminPanelStatus");

  let catalogState = modelCatalog || {};

  function populateFamilyOptions() {
    if (!familySelect) return;
    const families = Object.keys(catalogState || {});
    familySelect.innerHTML = families.map((family) => `<option value="${family}">${family}</option>`).join("");
    populateVersionOptions();
  }

  function populateVersionOptions() {
    if (!familySelect || !versionSelect) return;
    const family = familySelect.value;
    const versions = (((catalogState || {})[family] || {}).versions || []).map((item) => item.version);
    versionSelect.innerHTML = versions.map((version) => `<option value="${version}">${version}</option>`).join("");

    const active = (((catalogState || {})[family] || {}).active_version || "");
    if (active) versionSelect.value = active;
  }

  async function refreshCatalog() {
    if (!adminStatus) return;
    adminStatus.textContent = "Refreshing catalog...";
    try {
      const response = await fetch("/api/models");
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error("Failed to load model catalog");
      catalogState = data.data.catalog || {};
      populateFamilyOptions();
      adminStatus.textContent = "Catalog refreshed.";
    } catch (_error) {
      adminStatus.textContent = "Failed to refresh catalog.";
    }
  }

  if (familySelect) familySelect.addEventListener("change", populateVersionOptions);
  if (refreshCatalogBtn) refreshCatalogBtn.addEventListener("click", refreshCatalog);

  if (activateBtn) {
    activateBtn.addEventListener("click", async () => {
      if (!familySelect || !versionSelect || !adminStatus) return;
      adminStatus.textContent = "Activating version...";
      try {
        const response = await fetch("/api/models/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ family: familySelect.value, version: versionSelect.value }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error("Activation failed");
        adminStatus.textContent = `Active version updated to ${versionSelect.value}.`;
        await refreshCatalog();
      } catch (_error) {
        adminStatus.textContent = "Version activation failed.";
      }
    });
  }

  populateFamilyOptions();

  // Clinician notes and tags.
  const notesForm = document.getElementById("caseNoteForm");
  const requestIdInput = document.getElementById("caseRequestId");
  const tagsInput = document.getElementById("caseTags");
  const noteInput = document.getElementById("caseNote");
  const notesList = document.getElementById("caseNotesList");
  const notesStatus = document.getElementById("caseNoteStatus");
  const refreshNotesBtn = document.getElementById("refreshCaseNotesBtn");

  function renderNotes(notes) {
    if (!notesList) return;
    if (!notes || !notes.length) {
      notesList.innerHTML = '<div class="small text-muted">No notes added yet.</div>';
      return;
    }

    notesList.innerHTML = notes.map((item) => {
      const tags = (item.tags || []).map((tag) => `<span class="note-tag">${tag}</span>`).join("");
      return `
        <div class="note-item">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div class="small fw-semibold">${item.author || "Unknown"}</div>
            <div class="small text-muted">${String(item.created_at || "").replace("T", " ").slice(0, 19)}</div>
          </div>
          <div class="small mt-1">${item.note || ""}</div>
          <div class="note-tags mt-2">${tags}</div>
        </div>
      `;
    }).join("");
  }

  async function fetchCaseNotes() {
    const requestId = requestIdInput ? requestIdInput.value : "";
    if (!requestId) return;
    if (notesStatus) notesStatus.textContent = "Loading notes...";
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(requestId)}/notes`);
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error("Failed to load notes");
      renderNotes(data.data || []);
      if (notesStatus) notesStatus.textContent = `Loaded ${(data.data || []).length} note(s).`;
    } catch (_error) {
      if (notesStatus) notesStatus.textContent = "Unable to load notes.";
    }
  }

  if (refreshNotesBtn) {
    refreshNotesBtn.addEventListener("click", () => {
      fetchCaseNotes();
    });
  }

  if (notesForm) {
    notesForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const requestId = requestIdInput ? requestIdInput.value : "";
      const note = noteInput ? noteInput.value.trim() : "";
      const tags = (tagsInput ? tagsInput.value : "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

      if (!requestId || !note) {
        if (notesStatus) notesStatus.textContent = "Request ID and note are required.";
        return;
      }

      if (notesStatus) notesStatus.textContent = "Saving note...";
      try {
        const response = await fetch("/api/cases/annotate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: requestId, note, tags }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error("Note save failed");

        if (noteInput) noteInput.value = "";
        if (tagsInput) tagsInput.value = "";
        renderNotes(data.data || []);
        if (notesStatus) notesStatus.textContent = "Note saved.";
      } catch (_error) {
        if (notesStatus) notesStatus.textContent = "Failed to save note.";
      }
    });
  }

  fetchCaseNotes();
})();
