/* ============================================================
   MediAI - app.js
   ============================================================ */

function initParticles() {
  const container = document.querySelector('.particles');
  if (!container) return;

  for (let i = 0; i < 14; i += 1) {
    const particle = document.createElement('div');
    particle.className = 'particle';

    const size = Math.random() * 38 + 14;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.animationDuration = `${Math.random() * 14 + 12}s`;
    particle.style.animationDelay = `${Math.random() * 10}s`;

    container.appendChild(particle);
  }
}

function initCardAnimations() {
  const cards = document.querySelectorAll('.model-card');
  if (!cards.length) return;

  requestAnimationFrame(() => {
    cards.forEach((card, index) => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(12px)';
      card.style.transition = `opacity 0.35s ease ${index * 0.05}s, transform 0.35s ease ${index * 0.05}s`;

      requestAnimationFrame(() => {
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      });
    });
  });
}

function initSymptomSelector() {
  const search = document.getElementById('symptom-search');
  const items = document.querySelectorAll('.symptom-item');
  const counter = document.getElementById('symptom-counter');
  const selectedField = document.getElementById('selected-symptoms');

  if (!search || !counter || !selectedField) return;

  const selected = new Set();

  items.forEach((item) => {
    item.addEventListener('click', () => {
      const symptom = item.dataset.symptom;
      const check = item.querySelector('.symptom-check');
      if (!symptom || !check) return;

      if (selected.has(symptom)) {
        selected.delete(symptom);
        item.classList.remove('selected');
        check.innerHTML = '';
      } else {
        selected.add(symptom);
        item.classList.add('selected');
        check.innerHTML = '&#10003;';
      }

      counter.textContent = `${selected.size} symptom${selected.size !== 1 ? 's' : ''} selected`;
      selectedField.value = JSON.stringify(Array.from(selected));
    });
  });

  search.addEventListener('input', () => {
    const q = search.value.toLowerCase().replace(/\s+/g, '_');

    items.forEach((item) => {
      const text = item.textContent.toLowerCase();
      const symptom = item.dataset.symptom || '';
      const match = symptom.includes(q) || text.includes(q);
      item.classList.toggle('hidden', !match);
    });
  });
}

function clearSymptoms() {
  document.querySelectorAll('.symptom-item.selected').forEach((el) => el.click());
}

function selectCommon() {
  const common = ['fatigue', 'headache', 'nausea', 'high_fever', 'cough'];

  common.forEach((symptom) => {
    const item = document.querySelector(`[data-symptom="${symptom}"]`);
    if (item && !item.classList.contains('selected')) {
      item.click();
    }
  });
}

function initBMICompute() {
  const weight = document.getElementById('weight_kg');
  const height = document.getElementById('height_cm');
  const bmiField = document.getElementById('bmi_val');

  if (!weight || !height || !bmiField) return;

  const compute = () => {
    const w = parseFloat(weight.value);
    const hMeters = parseFloat(height.value) / 100;

    if (w > 0 && hMeters > 0) {
      bmiField.value = (w / (hMeters * hMeters)).toFixed(1);
    }
  };

  weight.addEventListener('input', compute);
  height.addEventListener('input', compute);
}

function initHRCompute() {
  const ageInput = document.getElementById('age_input');
  const thalachField = document.getElementById('thalach_field');

  if (!ageInput || !thalachField) return;

  ageInput.addEventListener('input', () => {
    if (!thalachField.dataset.edited) {
      const age = parseInt(ageInput.value || '0', 10);
      thalachField.value = Math.max(60, 220 - age);
    }
  });

  thalachField.addEventListener('input', () => {
    thalachField.dataset.edited = '1';
  });
}

function setMode(mode, btn) {
  const labSections = document.querySelectorAll('.lab-section');
  const form = document.getElementById('predict-form');
  const model = form?.dataset.model;

  labSections.forEach((section) => {
    section.classList.toggle('is-hidden', mode === 'quick');
  });

  const defaultsByModel = {
    diabetes: {
      Pregnancies: 0,
      Glucose: 100,
      BloodPressure: 80,
      SkinThickness: 20,
      Insulin: 80,
      BMI: 25,
      DiabetesPedigreeFunction: 0.2
    },
    heart: {
      trestbps: 130,
      chol: 200,
      fbs: 0,
      restecg: 0,
      thalach: 150,
      oldpeak: 0,
      slope: 1,
      ca: 0,
      thal: 2
    }
  };
  const defaults = defaultsByModel[model] || {};

  if (mode === 'quick') {
    Object.entries(defaults).forEach(([name, value]) => {
      const input = document.querySelector(`[name="${name}"]`);
      if (input) input.value = value;
    });
  }

  document.querySelectorAll('.mode-btn').forEach((node) => node.classList.remove('active'));
  if (btn) btn.classList.add('active');
}

function setPredictionStep(stepNumber) {
  const steps = document.querySelectorAll('.form-steps .step');
  if (!steps.length) return;

  steps.forEach((step) => {
    const value = Number(step.dataset.step || '0');
    step.classList.toggle('active', value <= stepNumber);
  });
}

function initFormSubmit() {
  const form = document.getElementById('predict-form');
  const overlay = document.getElementById('loading-overlay');

  if (!form || !overlay) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    setPredictionStep(2);
    overlay.classList.add('active');

    const data = {};
    new FormData(form).forEach((value, key) => {
      data[key] = value;
    });

    const symField = document.getElementById('selected-symptoms');
    if (symField) {
      data.symptoms = JSON.parse(symField.value || '[]');
    }

    const model = form.dataset.model;

    if (model === 'diabetes') {
      const diabetesDefaults = {
        Pregnancies: '0',
        Glucose: '100',
        BloodPressure: '80',
        SkinThickness: '20',
        Insulin: '80',
        BMI: '25',
        DiabetesPedigreeFunction: '0.2',
        Age: '35'
      };
      Object.entries(diabetesDefaults).forEach(([key, value]) => {
        if (data[key] === undefined || String(data[key]).trim() === '') data[key] = value;
      });
    }

    if (model === 'heart') {
      const heartDefaults = {
        age: '45',
        sex: '1',
        cp: '0',
        trestbps: '130',
        chol: '200',
        fbs: '0',
        restecg: '0',
        thalach: '150',
        exang: '0',
        oldpeak: '0',
        slope: '1',
        ca: '0',
        thal: '2'
      };
      Object.entries(heartDefaults).forEach(([key, value]) => {
        if (data[key] === undefined || String(data[key]).trim() === '') data[key] = value;
      });
    }

    try {
      const response = await fetch(`/predict/${model}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const result = await response.json();
      if (result.error) throw new Error(result.error);

      setPredictionStep(3);
      sessionStorage.setItem(
        'mediAI_result',
        JSON.stringify({ ...result, inputs: data, timestamp: new Date().toISOString() })
      );

      window.location.href = '/result';
    } catch (err) {
      overlay.classList.remove('active');
      setPredictionStep(1);

      const banner = document.getElementById('error-banner');
      if (banner) {
        banner.textContent = err.message || 'Prediction failed.';
        banner.style.display = 'block';
        banner.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  });
}

function initResultPage() {
  const raw = sessionStorage.getItem('mediAI_result');
  if (!raw) {
    window.location.href = '/';
    return;
  }

  renderResult(JSON.parse(raw));
}

function deriveRiskLevel(isPositive, confidence) {
  if (!isPositive) return { label: 'Low', css: 'risk-low' };
  if (confidence >= 0.8) return { label: 'High', css: 'risk-high' };
  return { label: 'Medium', css: 'risk-medium' };
}

function renderResult(result) {
  const positiveOutcomes = ['Diabetic', 'At Risk', 'Malignant'];
  const isPositive = positiveOutcomes.includes(result.prediction);
  const confidence = Number(result.confidence || 0.85);

  const banner = document.getElementById('result-banner');
  const bannerIcon = document.getElementById('banner-icon');
  const bannerResult = document.getElementById('banner-result');
  const bannerModel = document.getElementById('banner-model');
  const riskLevel = document.getElementById('risk-level');

  if (banner) banner.className = `result-banner ${isPositive ? 'at-risk' : 'healthy'}`;
  if (bannerIcon) bannerIcon.textContent = isPositive ? 'ALERT' : 'STABLE';
  if (bannerResult) bannerResult.textContent = result.prediction || 'N/A';
  if (bannerModel) bannerModel.textContent = modelLabel(result.model);

  if (riskLevel) {
    const risk = deriveRiskLevel(isPositive, confidence);
    riskLevel.textContent = risk.label;
    riskLevel.className = risk.css;
  }

  const pct = Math.round(confidence * 100);
  const pctNode = document.getElementById('gauge-pct');
  const gaugeFill = document.getElementById('gauge-fill');

  if (pctNode) pctNode.textContent = `${pct}%`;
  if (gaugeFill) {
    gaugeFill.className = `gauge-fill ${isPositive ? 'at-risk' : 'healthy'}`;
    setTimeout(() => {
      gaugeFill.style.strokeDashoffset = 408 - (408 * pct / 100);
    }, 120);
  }

  const btnNew = document.getElementById('btn-new');
  const btnNewBottom = document.getElementById('btn-new-bottom');
  if (btnNew) btnNew.href = `/predict/${result.model}`;
  if (btnNewBottom) btnNewBottom.href = `/predict/${result.model}`;

  renderCharts(result, isPositive);
  renderRecommendations(result, isPositive);
  renderSummary(result.inputs, result.model);
  renderTransparencyPanels(result);

  const reportBtn = document.getElementById('btn-report');
  if (reportBtn) {
    reportBtn.addEventListener('click', () => downloadReport(result));
  }
}

function renderCharts(result, isPositive) {
  const color = isPositive ? '#b42318' : '#1f8b4d';
  const colorAlpha = isPositive ? 'rgba(180,35,24,0.16)' : 'rgba(31,139,77,0.16)';

  if (window.Chart && Chart.defaults && Chart.defaults.font) {
    Chart.defaults.font.family = 'DM Sans';
  }

  if (result.model === 'diabetes') renderDiabetesCharts(result, color);
  else if (result.model === 'heart') renderHeartCharts(result, color, colorAlpha);
  else if (result.model === 'breast_cancer') renderBreastCharts(result, color);
  else if (result.model === 'disease') renderDiseaseCharts(result, color);
}

function renderDiabetesCharts(result, color) {
  const inp = result.inputs || {};

  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: ['Glucose', 'Blood Pressure', 'BMI', 'Insulin'],
      datasets: [
        {
          label: 'Your values',
          data: [inp.Glucose, inp.BloodPressure, inp.BMI, inp.Insulin].map(Number),
          backgroundColor: color,
          borderRadius: 6
        },
        {
          label: 'Reference range',
          data: [99, 80, 24.9, 100],
          backgroundColor: 'rgba(15,118,110,0.65)',
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { y: { grid: { color: '#ecf1f8' } } }
    }
  });

  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Glucose impact', 'BMI impact', 'Age impact', 'Other factors'],
      datasets: [{
        data: [35, 25, 20, 20],
        backgroundColor: ['#b42318', '#dc2626', '#f59e0b', '#0f766e'],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderHeartCharts(result, color, colorAlpha) {
  const inp = result.inputs || {};

  new Chart(document.getElementById('chart-main'), {
    type: 'radar',
    data: {
      labels: ['Age risk', 'Cholesterol', 'Blood pressure', 'Heart rate', 'ST depression'],
      datasets: [{
        label: 'Profile',
        data: [
          normalize(inp.age, 30, 80),
          normalize(inp.chol, 100, 350),
          normalize(inp.trestbps, 80, 200),
          normalize(inp.thalach, 60, 220),
          normalize(inp.oldpeak, 0, 6)
        ],
        backgroundColor: colorAlpha,
        borderColor: color,
        pointBackgroundColor: color,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { r: { min: 0, max: 1, ticks: { display: false } } }
    }
  });

  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Cholesterol', 'Blood pressure', 'Age', 'ECG', 'Lifestyle'],
      datasets: [{
        data: [28, 22, 20, 15, 15],
        backgroundColor: ['#b42318', '#dc2626', '#f59e0b', '#0f766e', '#2563eb'],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderBreastCharts(result, color) {
  const inp = result.inputs || {};
  const keys = ['radius_mean', 'texture_mean', 'perimeter_mean', 'smoothness_mean', 'concavity_mean'];

  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: keys.map((k) => k.replace('_mean', '').replace(/_/g, ' ')),
      datasets: [{
        label: 'Your values',
        data: keys.map((k) => parseFloat(inp[k]) || 0),
        backgroundColor: color,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } }
    }
  });

  const confidence = Number(result.confidence || 0.85);

  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Benign probability', 'Malignant probability'],
      datasets: [{
        data: result.prediction === 'Malignant'
          ? [Math.round((1 - confidence) * 100), Math.round(confidence * 100)]
          : [Math.round(confidence * 100), Math.round((1 - confidence) * 100)],
        backgroundColor: ['#1f8b4d', '#b42318'],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderDiseaseCharts(result, color) {
  const symptoms = (result.inputs && result.inputs.symptoms) || [];

  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: symptoms.slice(0, 8).map((s) => s.replace(/_/g, ' ')),
      datasets: [{
        label: 'Matched symptoms',
        data: symptoms.slice(0, 8).map(() => 1),
        backgroundColor: color,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false } }
    }
  });

  const confidence = Number(result.confidence || 0.85);

  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Match confidence', 'Uncertainty'],
      datasets: [{
        data: [Math.round(confidence * 100), Math.round((1 - confidence) * 100)],
        backgroundColor: [color, '#dbe3ef'],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

const RECS = {
  diabetes: {
    positive: {
      precautions: [
        { icon: '!', text: 'Check fasting glucose routinely and track trends over time.' },
        { icon: '!', text: 'Limit high-glycemic foods and reduce refined sugar intake.' },
        { icon: '!', text: 'Include at least 30 minutes of daily physical activity.' }
      ],
      recommendations: [
        { icon: '+', text: 'Discuss medication options with your physician if needed.' },
        { icon: '+', text: 'Use a balanced meal plan focused on fiber and lean proteins.' },
        { icon: '+', text: 'Schedule regular HbA1c checks for long-term monitoring.' }
      ]
    },
    negative: {
      precautions: [
        { icon: 'i', text: 'Maintain healthy BMI and regular activity to keep risk low.' },
        { icon: 'i', text: 'Repeat preventive blood tests annually.' }
      ],
      recommendations: [
        { icon: '+', text: 'Continue a balanced diet with controlled sugar intake.' },
        { icon: '+', text: 'Maintain routine preventive care visits.' }
      ]
    }
  },
  heart: {
    positive: {
      precautions: [
        { icon: '!', text: 'Arrange a prompt cardiology follow-up for full evaluation.' },
        { icon: '!', text: 'Control blood pressure, lipids, and smoking risk factors.' },
        { icon: '!', text: 'Seek urgent care if chest pain or breathing symptoms occur.' }
      ],
      recommendations: [
        { icon: '+', text: 'Follow a clinician-approved heart-friendly exercise routine.' },
        { icon: '+', text: 'Adopt a low-sodium, high-fiber meal pattern.' }
      ]
    },
    negative: {
      precautions: [
        { icon: 'i', text: 'Keep monitoring blood pressure and cholesterol periodically.' },
        { icon: 'i', text: 'Continue preventive lifestyle habits.' }
      ],
      recommendations: [
        { icon: '+', text: 'Maintain regular aerobic exercise each week.' },
        { icon: '+', text: 'Continue annual preventive screening.' }
      ]
    }
  },
  breast_cancer: {
    positive: {
      precautions: [
        { icon: '!', text: 'Consult an oncologist for diagnostic confirmation.' },
        { icon: '!', text: 'Use this result only as screening guidance.' }
      ],
      recommendations: [
        { icon: '+', text: 'Discuss imaging and biopsy plan with a specialist.' },
        { icon: '+', text: 'Coordinate follow-up timelines early.' }
      ]
    },
    negative: {
      precautions: [
        { icon: 'i', text: 'Continue routine screening as advised for your age group.' },
        { icon: 'i', text: 'Report any new breast changes promptly.' }
      ],
      recommendations: [
        { icon: '+', text: 'Maintain healthy weight and active lifestyle.' },
        { icon: '+', text: 'Keep regular preventive appointments.' }
      ]
    }
  },
  disease: {
    precautions: [
      { icon: '!', text: 'Use this output as preliminary screening only.' },
      { icon: '!', text: 'Consult a physician for clinical confirmation.' },
      { icon: '!', text: 'Seek care promptly if symptoms worsen.' }
    ],
    recommendations: [
      { icon: '+', text: 'Track symptom changes daily.' },
      { icon: '+', text: 'Maintain hydration, rest, and balanced nutrition.' }
    ]
  }
};

function renderRecommendations(result, isPositive) {
  const modelKey = result.model;
  const data = modelKey === 'disease'
    ? RECS.disease
    : ((RECS[modelKey] || {})[isPositive ? 'positive' : 'negative'] || RECS.disease);

  const build = (items) => items.map((item) => `<li data-icon="${item.icon}">${item.text}</li>`).join('');

  const precautions = document.getElementById('rec-precautions');
  const recommendations = document.getElementById('rec-recommendations');

  if (precautions && data.precautions) precautions.innerHTML = build(data.precautions);
  if (recommendations && data.recommendations) recommendations.innerHTML = build(data.recommendations);
}

function renderSummary(inputs, model) {
  const tbody = document.getElementById('summary-tbody');
  if (!tbody) return;

  const exclude = ['symptoms', 'weight_kg', 'height_cm', 'dpf_helper'];
  const labels = {
    age: 'Age',
    sex: 'Sex',
    chol: 'Cholesterol',
    trestbps: 'Blood pressure',
    thalach: 'Max heart rate',
    Glucose: 'Glucose',
    BMI: 'BMI',
    Pregnancies: 'Pregnancies',
    BloodPressure: 'Blood pressure (diastolic)',
    Insulin: 'Insulin',
    Age: 'Age'
  };

  let rows = '';

  if (model === 'disease') {
    const symptoms = (inputs && inputs.symptoms) || [];
    const summary = symptoms.length ? symptoms.map((s) => s.replace(/_/g, ' ')).join(', ') : 'None selected';
    rows = `<tr><td>Symptoms selected</td><td>${summary}</td></tr>`;
  } else {
    Object.entries(inputs || {}).forEach(([key, value]) => {
      if (!exclude.includes(key)) {
        rows += `<tr><td>${labels[key] || key}</td><td>${value}</td></tr>`;
      }
    });
  }

  tbody.innerHTML = rows;
}

function initRecTabs() {
  const tabs = document.querySelectorAll('.rec-tab');
  if (!tabs.length) return;

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.rec-tab').forEach((node) => node.classList.remove('active'));
      document.querySelectorAll('.rec-panel').forEach((panel) => panel.classList.remove('active'));

      tab.classList.add('active');
      const panel = document.getElementById(tab.dataset.panel);
      if (panel) panel.classList.add('active');
    });
  });
}

async function downloadReport(result) {
  const button = document.getElementById('btn-report');
  if (!button) return;

  const originalLabel = button.textContent;
  button.textContent = 'Generating report...';
  button.disabled = true;

  const chartMainB64 = document.getElementById('chart-main')?.toDataURL('image/png');
  const chartPieB64 = document.getElementById('chart-pie')?.toDataURL('image/png');

  try {
    const response = await fetch('/report/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...result, chart_main: chartMainB64, chart_pie: chartPieB64 })
    });

    const data = await response.json();
    if (data.report_url) {
      window.location.href = data.report_url;
    }
  } catch (err) {
    alert(`Report generation failed: ${err.message}`);
  } finally {
    button.textContent = originalLabel;
    button.disabled = false;
  }
}

function normalize(value, min, max) {
  return Math.min(1, Math.max(0, (parseFloat(value || 0) - min) / (max - min)));
}

function modelLabel(model) {
  const labels = {
    diabetes: 'Diabetes Predictor',
    heart: 'Heart Disease Predictor',
    breast_cancer: 'Breast Cancer Predictor',
    disease: 'Disease Symptom Predictor'
  };

  return labels[model] || model;
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function toHumanLabel(key) {
  const explicit = {
    auc_roc: 'AUC-ROC',
    false_positive_rate: 'False Positive Rate',
    false_negative_rate: 'False Negative Rate',
    f1_score: 'F1 Score',
    ppv: 'Precision (PPV)',
    npv: 'Negative Predictive Value'
  };
  const normalized = String(key || '').trim();
  if (explicit[normalized]) return explicit[normalized];
  return normalized
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPercentage(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMetricValue(key, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return '-';

  const isProbabilityLikeMetric = /(rate|accuracy|sensitivity|specificity|auc|precision|recall|f1|ppv|npv)/i.test(String(key));

  if (Array.isArray(rawValue)) {
    const values = rawValue.map((item) => Number(item));
    const allNumeric = values.length > 0 && values.every((item) => Number.isFinite(item));
    if (!allNumeric) return rawValue.join(', ');

    if (values.length >= 3) {
      const center = values[0];
      const lower = values[1];
      const upper = values[2];
      if (Math.abs(center) <= 1 && Math.abs(lower) <= 1 && Math.abs(upper) <= 1) {
        return `${formatPercentage(center)} (${formatPercentage(lower)}-${formatPercentage(upper)})`;
      }
      return `${center.toFixed(3)} (${lower.toFixed(3)}-${upper.toFixed(3)})`;
    }

    return values
      .map((item) => ((Math.abs(item) <= 1 && isProbabilityLikeMetric) ? formatPercentage(item) : item.toFixed(3)))
      .join(', ');
  }

  if (typeof rawValue === 'object') {
    const valueObject = asObject(rawValue);
    if ('value' in valueObject) {
      return formatMetricValue(key, valueObject.value);
    }
    const compact = Object.entries(valueObject)
      .slice(0, 3)
      .map(([entryKey, entryValue]) => `${toHumanLabel(entryKey)}: ${entryValue}`);
    return compact.length ? compact.join(' | ') : '-';
  }

  const numeric = Number(rawValue);
  if (Number.isFinite(numeric)) {
    if (Math.abs(numeric) <= 1 && isProbabilityLikeMetric) return formatPercentage(numeric);
    return numeric.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  return String(rawValue);
}

function renderSimpleList(listNode, items, fallbackText) {
  if (!listNode) return;
  listNode.innerHTML = '';

  const rows = Array.isArray(items) ? items.filter((item) => String(item || '').trim() !== '') : [];
  if (!rows.length) rows.push(fallbackText);

  rows.forEach((text) => {
    const line = String(text);
    const li = document.createElement('li');
    li.dataset.icon = /(warn|risk|caution|false negative|missing|outside|outlier|error)/i.test(line) ? '!' : 'i';
    li.textContent = line;
    listNode.appendChild(li);
  });
}

function renderPerformanceMetrics(performanceMetrics) {
  const tbody = document.getElementById('metrics-tbody');
  if (!tbody) return;

  tbody.innerHTML = '';
  const metrics = asObject(performanceMetrics);
  const entries = Object.entries(metrics);
  const metricOrder = [
    'accuracy',
    'sensitivity',
    'specificity',
    'auc_roc',
    'precision',
    'recall',
    'f1_score',
    'ppv',
    'npv',
    'false_positive_rate',
    'false_negative_rate'
  ];

  entries.sort(([a], [b]) => {
    const aIndex = metricOrder.indexOf(a);
    const bIndex = metricOrder.indexOf(b);
    if (aIndex !== -1 || bIndex !== -1) {
      const safeA = aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex;
      const safeB = bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex;
      return safeA - safeB;
    }
    return a.localeCompare(b);
  });

  if (!entries.length) {
    const row = document.createElement('tr');
    const metricCell = document.createElement('td');
    const valueCell = document.createElement('td');
    metricCell.textContent = '-';
    valueCell.textContent = 'No model metrics available for this run.';
    row.append(metricCell, valueCell);
    tbody.appendChild(row);
    return;
  }

  entries.forEach(([key, value]) => {
    const row = document.createElement('tr');
    const metricCell = document.createElement('td');
    const valueCell = document.createElement('td');
    metricCell.textContent = toHumanLabel(key);
    valueCell.textContent = formatMetricValue(key, value);
    row.append(metricCell, valueCell);
    tbody.appendChild(row);
  });
}

function formatContribution(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  if (Math.abs(numeric) <= 1) {
    return `${numeric > 0 ? '+' : ''}${(numeric * 100).toFixed(1)}%`;
  }
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}`;
}

function renderExplainability(explainabilityPayload) {
  const explainability = asObject(explainabilityPayload);
  const summaryNode = document.getElementById('explainability-summary');
  const featureContrib = document.getElementById('feature-contrib');

  if (summaryNode) {
    summaryNode.textContent = String(explainability.summary || 'Feature analysis unavailable.');
  }

  if (!featureContrib) return;

  featureContrib.innerHTML = '';
  const contributions = asObject(explainability.feature_contributions);
  const entries = Object.entries(contributions)
    .map(([name, value]) => [name, Number(value)])
    .filter(([, value]) => Number.isFinite(value))
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

  if (!entries.length) {
    const chip = document.createElement('span');
    chip.className = 'contrib-chip';
    chip.textContent = 'No feature contributions available.';
    featureContrib.appendChild(chip);
    return;
  }

  entries.slice(0, 8).forEach(([name, value]) => {
    const chip = document.createElement('span');
    chip.className = `contrib-chip ${value >= 0 ? 'positive' : 'negative'}`;
    chip.textContent = `${toHumanLabel(name)} ${formatContribution(value)}`;
    featureContrib.appendChild(chip);
  });
}

function renderInputQualityChecks(dataQualityPayload, validationPayload) {
  const qualityList = document.getElementById('quality-list');
  if (!qualityList) return;

  const dataQuality = asObject(dataQualityPayload);
  const validation = asObject(validationPayload);
  const requiredCheck = asObject(dataQuality.required_field_check);
  const lines = [];

  if (typeof requiredCheck.is_sufficient === 'boolean') {
    if (requiredCheck.is_sufficient === false) {
      const missing = Array.isArray(requiredCheck.missing_critical) ? requiredCheck.missing_critical : [];
      if (missing.length) lines.push(`Missing required fields detected: ${missing.join(', ')}.`);
    } else {
      lines.push('Required field check passed.');
    }
  }

  const imputedFields = Array.isArray(dataQuality.imputed_fields) ? dataQuality.imputed_fields : [];
  if (imputedFields.length) {
    lines.push(`Imputed values used for: ${imputedFields.join(', ')}.`);
  }

  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  errors.slice(0, 2).forEach((item) => {
    const message = asObject(item).message;
    if (message) lines.push(String(message));
  });

  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  warnings.slice(0, 2).forEach((item) => {
    const message = asObject(item).message;
    if (message) lines.push(String(message));
  });

  const outliers = Array.isArray(validation.outliers) ? validation.outliers : [];
  if (outliers.length) {
    const names = outliers
      .map((item) => asObject(item).field)
      .filter((name) => typeof name === 'string' && name.trim() !== '')
      .slice(0, 3);
    if (names.length) lines.push(`Potential outlier inputs: ${names.join(', ')}.`);
  }

  renderSimpleList(qualityList, lines, 'Input quality checks found no major issues.');
}

function renderTransparencyPanels(result) {
  const disclosure = asObject(result.disclosure);
  const modelInfo = asObject(result.model_info);
  const limitations = Array.isArray(result.limitations) ? result.limitations : [];

  const disclosureHeadlineNode = document.getElementById('disclosure-headline');
  if (disclosureHeadlineNode) {
    disclosureHeadlineNode.textContent = String(
      disclosure.headline || disclosure.dataset_disclosure || 'Model disclosure details are listed below.'
    );
  }

  const disclosureLines = [];
  if (disclosure.dataset_disclosure) disclosureLines.push(String(disclosure.dataset_disclosure));
  if (disclosure.error_margin_note) disclosureLines.push(String(disclosure.error_margin_note));
  if (result.confidence_range) disclosureLines.push(`Calibrated confidence range: ${result.confidence_range}.`);
  if (modelInfo.algorithm) disclosureLines.push(`Model algorithm: ${modelInfo.algorithm}.`);

  const trainingDataset = asObject(modelInfo.training_dataset);
  if (trainingDataset.name) {
    const cases = trainingDataset.cases !== undefined ? ` (${trainingDataset.cases} cases)` : '';
    disclosureLines.push(`Training dataset: ${trainingDataset.name}${cases}.`);
  }
  if (trainingDataset.demographics) {
    disclosureLines.push(`Dataset demographics: ${trainingDataset.demographics}.`);
  }
  if (limitations.length) disclosureLines.push(`Limitation: ${String(limitations[0])}`);

  renderSimpleList(
    document.getElementById('disclosure-list'),
    disclosureLines,
    'No additional disclosure details were provided for this run.'
  );
  renderPerformanceMetrics(result.performance_metrics);
  renderExplainability(result.explainability);
  renderInputQualityChecks(result.data_quality, result.validation);
}

document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  initCardAnimations();
  initSymptomSelector();
  initBMICompute();
  initHRCompute();
  initFormSubmit();
  initRecTabs();

  if (document.getElementById('result-banner')) {
    initResultPage();
  }
});
