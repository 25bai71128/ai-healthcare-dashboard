/* ============================================================
   MediAI — app.js
   ============================================================ */

// Floating Particles
function initParticles() {
  const container = document.querySelector('.particles');
  if (!container) return;
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = Math.random() * 60 + 20;
    p.style.cssText = `
      width:${size}px; height:${size}px;
      left:${Math.random()*100}%;
      animation-duration:${Math.random()*20+15}s;
      animation-delay:${Math.random()*20}s;
    `;
    container.appendChild(p);
  }
}

// Staggered card animations
function initCardAnimations() {
  // Delay animation until after first paint so grid layout is not disrupted
  requestAnimationFrame(() => {
    setTimeout(() => {
      document.querySelectorAll('.model-card').forEach((card, i) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `opacity 0.5s ease ${i * 0.1}s, transform 0.5s ease ${i * 0.1}s`;
        requestAnimationFrame(() => {
          card.style.opacity = '1';
          card.style.transform = 'translateY(0)';
        });
      });
    }, 50);
  });
}

// Symptom Search & Selection
function initSymptomSelector() {
  const search  = document.getElementById('symptom-search');
  const items   = document.querySelectorAll('.symptom-item');
  const counter = document.getElementById('symptom-counter');
  if (!search) return;

  let selected = new Set();

  items.forEach(item => {
    item.addEventListener('click', () => {
      const sym = item.dataset.symptom;
      if (selected.has(sym)) {
        selected.delete(sym);
        item.classList.remove('selected');
        item.querySelector('.symptom-check').innerHTML = '';
      } else {
        selected.add(sym);
        item.classList.add('selected');
        item.querySelector('.symptom-check').innerHTML = '✓';
      }
      counter.textContent = `${selected.size} symptom${selected.size !== 1 ? 's' : ''} selected`;
      document.getElementById('selected-symptoms').value = JSON.stringify([...selected]);
    });
  });

  search.addEventListener('input', () => {
    const q = search.value.toLowerCase().replace(/\s+/g, '_');
    items.forEach(item => {
      const match = item.dataset.symptom.includes(q) || item.textContent.toLowerCase().includes(q);
      item.classList.toggle('hidden', !match);
    });
  });
}

// Clear all symptoms
function clearSymptoms() {
  document.querySelectorAll('.symptom-item.selected').forEach(el => el.click());
}

// Select common symptoms
function selectCommon() {
  ['fatigue','headache','nausea','high_fever','cough'].forEach(sym => {
    const el = document.querySelector(`[data-symptom="${sym}"]`);
    if (el && !el.classList.contains('selected')) el.click();
  });
}

// BMI Auto-compute
function initBMICompute() {
  const w = document.getElementById('weight_kg');
  const h = document.getElementById('height_cm');
  const bmiField = document.getElementById('bmi_val');
  if (!w || !h || !bmiField) return;
  function compute() {
    const wv = parseFloat(w.value), hv = parseFloat(h.value) / 100;
    if (wv > 0 && hv > 0) bmiField.value = (wv / (hv * hv)).toFixed(1);
  }
  w.addEventListener('input', compute);
  h.addEventListener('input', compute);
}

// Max Heart Rate Auto-compute
function initHRCompute() {
  const ageInput    = document.getElementById('age_input');
  const thalachField = document.getElementById('thalach_field');
  if (!ageInput || !thalachField) return;
  ageInput.addEventListener('input', () => {
    if (!thalachField.dataset.edited) {
      thalachField.value = Math.max(60, 220 - parseInt(ageInput.value || 0));
    }
  });
  thalachField.addEventListener('input', () => { thalachField.dataset.edited = '1'; });
}

// Quick / Detailed Mode Toggle
function setMode(mode, btn) {
  document.querySelectorAll('.lab-section').forEach(el => {
    el.style.display = mode === 'quick' ? 'none' : 'block';
  });
  const defaults = { trestbps:130, chol:200, thalach:150, oldpeak:0, restecg:0, slope:1, thal:2, ca:0, SkinThickness:20, Insulin:80 };
  if (mode === 'quick') {
    Object.entries(defaults).forEach(([k, v]) => {
      const el = document.querySelector(`[name="${k}"]`);
      if (el) el.value = v;
    });
  }
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// Form Submission with Loading
function initFormSubmit() {
  const form    = document.getElementById('predict-form');
  const overlay = document.getElementById('loading-overlay');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    overlay.classList.add('active');
    const data = {};
    new FormData(form).forEach((v, k) => { data[k] = v; });
    const symField = document.getElementById('selected-symptoms');
    if (symField) data.symptoms = JSON.parse(symField.value || '[]');
    const model = form.dataset.model;

    try {
      const res = await fetch(`/predict/${model}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const result = await res.json();
      if (result.error) throw new Error(result.error);
      sessionStorage.setItem('mediAI_result', JSON.stringify({ ...result, inputs: data, timestamp: new Date().toISOString() }));
      window.location.href = '/result';
    } catch (err) {
      overlay.classList.remove('active');
      const eb = document.getElementById('error-banner');
      if (eb) { eb.textContent = err.message; eb.style.display = 'block'; eb.scrollIntoView({ behavior: 'smooth' }); }
    }
  });
}

// Result Page Init
function initResultPage() {
  const raw = sessionStorage.getItem('mediAI_result');
  if (!raw) { window.location.href = '/'; return; }
  renderResult(JSON.parse(raw));
}

function renderResult(result) {
  const isPositive = ['Diabetic','At Risk','Malignant'].includes(result.prediction);
  const banner = document.getElementById('result-banner');
  banner.className = `result-banner ${isPositive ? 'at-risk' : 'healthy'}`;
  document.getElementById('banner-icon').textContent   = isPositive ? '⚠️' : '✅';
  document.getElementById('banner-result').textContent = result.prediction;
  document.getElementById('banner-model').textContent  = modelLabel(result.model);

  const pct  = Math.round((result.confidence || 0.85) * 100);
  document.getElementById('gauge-pct').textContent = pct + '%';
  const fill = document.getElementById('gauge-fill');
  fill.className = `gauge-fill ${isPositive ? 'at-risk' : 'healthy'}`;
  setTimeout(() => { fill.style.strokeDashoffset = 408 - (408 * pct / 100); }, 100);

  // Set New Assessment link to same model
  const btnNew = document.getElementById('btn-new');
  const btnNewBottom = document.getElementById('btn-new-bottom');
  if (btnNew) btnNew.href = `/predict/${result.model}`;
  if (btnNewBottom) btnNewBottom.href = `/predict/${result.model}`;

  renderCharts(result, isPositive);
  renderRecommendations(result, isPositive);
  renderSummary(result.inputs, result.model);
  document.getElementById('btn-report').addEventListener('click', () => downloadReport(result));
}

// Chart Rendering
function renderCharts(result, isPositive) {
  const color      = isPositive ? '#E53E3E' : '#38A169';
  const colorAlpha = isPositive ? 'rgba(229,62,62,0.15)' : 'rgba(56,161,105,0.15)';
  Chart.defaults.font.family = 'DM Sans';

  if (result.model === 'diabetes')      renderDiabetesCharts(result, color, colorAlpha);
  else if (result.model === 'heart')    renderHeartCharts(result, color, colorAlpha);
  else if (result.model === 'breast_cancer') renderBreastCharts(result, color, colorAlpha);
  else if (result.model === 'disease')  renderDiseaseCharts(result, color, colorAlpha);
}

function renderDiabetesCharts(result, color, colorAlpha) {
  const inp = result.inputs;
  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: ['Glucose', 'Blood Pressure', 'BMI', 'Insulin'],
      datasets: [
        { label: 'Your Values', data: [inp.Glucose, inp.BloodPressure, inp.BMI, inp.Insulin].map(Number), backgroundColor: color, borderRadius: 6 },
        { label: 'Normal Range', data: [99, 80, 24.9, 100], backgroundColor: 'rgba(0,180,166,0.6)', borderRadius: 6 }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { y: { grid: { color: '#F0F4F8' } } } }
  });
  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Glucose Impact', 'BMI Impact', 'Age Impact', 'Other Factors'],
      datasets: [{ data: [35, 25, 20, 20], backgroundColor: ['#E53E3E','#FF6B6B','#FFD93D','#00B4A6'], borderWidth: 0, hoverOffset: 8 }]
    },
    options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom' } } }
  });
}

function renderHeartCharts(result, color, colorAlpha) {
  const inp = result.inputs;
  new Chart(document.getElementById('chart-main'), {
    type: 'radar',
    data: {
      labels: ['Age Risk', 'Cholesterol', 'Blood Pressure', 'Heart Rate', 'ST Depression'],
      datasets: [{
        label: 'Your Profile',
        data: [
          normalize(inp.age, 30, 80), normalize(inp.chol, 100, 350),
          normalize(inp.trestbps, 80, 200), normalize(inp.thalach, 60, 220), normalize(inp.oldpeak, 0, 6)
        ],
        backgroundColor: colorAlpha, borderColor: color, pointBackgroundColor: color, borderWidth: 2
      }]
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { r: { min: 0, max: 1, ticks: { display: false } } } }
  });
  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Cholesterol', 'Blood Pressure', 'Age', 'ECG', 'Lifestyle'],
      datasets: [{ data: [28,22,20,15,15], backgroundColor: ['#E53E3E','#FF6B6B','#FFD93D','#00B4A6','#9F7AEA'], borderWidth: 0, hoverOffset: 8 }]
    },
    options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom' } } }
  });
}

function renderBreastCharts(result, color, colorAlpha) {
  const inp = result.inputs;
  const keys = ["radius_mean", "texture_mean", "perimeter_mean", "smoothness_mean", "concavity_mean"];
  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: keys.map((k) => k.replace("_mean", "").replace(/_/g, " ")),
      datasets: [{ label: 'Your Values', data: keys.map((k) => parseFloat(inp[k]) || 0), backgroundColor: color, borderRadius: 6 }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
  });
  const conf = result.confidence || 0.85;
  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Benign Probability', 'Malignant Probability'],
      datasets: [{
        data: result.prediction === 'Malignant'
          ? [Math.round((1-conf)*100), Math.round(conf*100)]
          : [Math.round(conf*100), Math.round((1-conf)*100)],
        backgroundColor: ['#38A169','#E53E3E'], borderWidth: 0, hoverOffset: 8
      }]
    },
    options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom' } } }
  });
}

function renderDiseaseCharts(result, color, colorAlpha) {
  const symptoms = result.inputs.symptoms || [];
  new Chart(document.getElementById('chart-main'), {
    type: 'bar',
    data: {
      labels: symptoms.slice(0,8).map(s => s.replace(/_/g,' ')),
      datasets: [{ label: 'Matched Symptoms', data: symptoms.slice(0,8).map(()=>1), backgroundColor: color, borderRadius: 6 }]
    },
    options: { indexAxis:'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false } } }
  });
  const conf = result.confidence || 0.85;
  new Chart(document.getElementById('chart-pie'), {
    type: 'doughnut',
    data: {
      labels: ['Match Confidence', 'Uncertainty'],
      datasets: [{ data: [Math.round(conf*100), Math.round((1-conf)*100)], backgroundColor: [color,'#E2E8F0'], borderWidth: 0, hoverOffset: 8 }]
    },
    options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'bottom' } } }
  });
}

// Recommendations Data
const RECS = {
  diabetes: {
    positive: {
      precautions: [
        { icon:'🩸', text:'Monitor blood sugar daily — aim for fasting glucose below 100 mg/dL' },
        { icon:'🥗', text:'Avoid refined sugars, white bread, and high-glycemic foods' },
        { icon:'🏃', text:'Exercise at least 30 minutes per day (brisk walking, cycling)' },
        { icon:'💧', text:'Drink 8+ glasses of water daily to aid glucose regulation' },
        { icon:'🧪', text:'Get HbA1c tested every 3 months to track long-term sugar control' },
      ],
      recommendations: [
        { icon:'🥦', text:'Follow a low-glycemic diet: vegetables, legumes, whole grains, lean proteins' },
        { icon:'⚖️', text:'Even 5–10% weight loss significantly improves insulin sensitivity' },
        { icon:'💊', text:'Consult a doctor about metformin or GLP-1 agonists if diet alone is insufficient' },
        { icon:'👣', text:'Inspect feet daily — diabetic neuropathy can cause unnoticed wounds' },
        { icon:'🏥', text:'Schedule annual eye and kidney function exams to catch complications early' },
      ]
    },
    negative: {
      precautions: [
        { icon:'✅', text:'Maintain a healthy weight (BMI 18.5–24.9) to keep diabetes risk low' },
        { icon:'🥗', text:'Limit processed sugar and refined carbohydrates in your diet' },
        { icon:'🏃', text:'Stay active — 150 minutes of moderate exercise per week is recommended' },
      ],
      recommendations: [
        { icon:'🧪', text:'Get a fasting glucose test annually as a preventive screen' },
        { icon:'🌿', text:'Consider a Mediterranean-style diet for long-term metabolic health' },
      ]
    }
  },
  heart: {
    positive: {
      precautions: [
        { icon:'❤️', text:'Seek immediate cardiology consultation — do not delay' },
        { icon:'🚭', text:'Stop smoking immediately — it doubles heart disease risk' },
        { icon:'🧂', text:'Reduce sodium intake to under 2,300 mg/day to lower blood pressure' },
        { icon:'😴', text:'Ensure 7–9 hours of sleep — poor sleep increases cardiac risk' },
        { icon:'🚨', text:'Know heart attack symptoms: chest pain, left arm pain, shortness of breath' },
      ],
      recommendations: [
        { icon:'💊', text:'Discuss statins or antihypertensives with your cardiologist' },
        { icon:'🏊', text:'Low-impact exercise (swimming, walking) strengthens the heart safely' },
        { icon:'🥑', text:'Adopt a heart-healthy diet: olive oil, fish, nuts, fruits, vegetables' },
        { icon:'🧘', text:'Practice stress reduction — chronic stress elevates cortisol and damages arteries' },
      ]
    },
    negative: {
      precautions: [
        { icon:'✅', text:'Maintain a heart-healthy lifestyle to preserve your good results' },
        { icon:'📊', text:'Check cholesterol and blood pressure annually' },
      ],
      recommendations: [
        { icon:'🏃', text:'Continue regular aerobic exercise — aim for 150 min/week' },
        { icon:'🐟', text:'Eat fatty fish (salmon, mackerel) twice a week for omega-3 benefits' },
      ]
    }
  },
  breast_cancer: {
    positive: {
      precautions: [
        { icon:'🏥', text:'Consult an oncologist immediately for biopsy confirmation' },
        { icon:'📋', text:'This is a screening tool only — clinical diagnosis is required' },
        { icon:'🔬', text:'Request a mammogram and ultrasound if not already done' },
      ],
      recommendations: [
        { icon:'💪', text:'Stay physically active — exercise reduces recurrence risk by up to 40%' },
        { icon:'🥦', text:'Eat cruciferous vegetables (broccoli, kale) — contain cancer-fighting compounds' },
        { icon:'🧠', text:'Seek psychological support — a diagnosis affects mental health significantly' },
      ]
    },
    negative: {
      precautions: [
        { icon:'✅', text:'Result suggests benign characteristics, but follow up with a doctor' },
        { icon:'📅', text:'Schedule annual mammograms starting at age 40' },
      ],
      recommendations: [
        { icon:'🏃', text:'Maintain a healthy weight — obesity is a risk factor for breast cancer' },
        { icon:'🍷', text:'Limit alcohol — even moderate drinking is linked to increased risk' },
      ]
    }
  },
  disease: {
    precautions: [
      { icon:'🏥', text:'Consult a doctor to confirm the diagnosis with proper clinical tests' },
      { icon:'💊', text:'Do not self-medicate — use this result only as a starting guide' },
      { icon:'🌡️', text:'Track your symptoms and note any that worsen or improve over time' },
      { icon:'💧', text:'Stay hydrated and get adequate rest while managing symptoms' },
    ],
    recommendations: [
      { icon:'📋', text:'Bring this result to your doctor\'s appointment for discussion' },
      { icon:'🥗', text:'Maintain a nutritious diet to support your immune system' },
      { icon:'😴', text:'Ensure 7–9 hours of quality sleep to support recovery' },
    ]
  }
};

function renderRecommendations(result, isPositive) {
  const key = result.model;
  let recs = key === 'disease' ? RECS.disease : ((RECS[key] || {})[isPositive ? 'positive' : 'negative'] || RECS.disease);
  const build = items => items.map((item, i) =>
    `<li data-icon="${item.icon}" style="animation-delay:${i*0.07}s">${item.text}</li>`
  ).join('');
  const precEl = document.getElementById('rec-precautions');
  const recEl  = document.getElementById('rec-recommendations');
  if (precEl && recs.precautions)      precEl.innerHTML = build(recs.precautions);
  if (recEl  && recs.recommendations)  recEl.innerHTML  = build(recs.recommendations);
}

function renderSummary(inputs, model) {
  const tbody = document.getElementById('summary-tbody');
  if (!tbody) return;
  const exclude = ['symptoms','weight_kg','height_cm','dpf_helper'];
  const labels = { age:'Age', sex:'Sex', chol:'Cholesterol', trestbps:'Blood Pressure', thalach:'Max Heart Rate', Glucose:'Glucose', BMI:'BMI', Pregnancies:'Pregnancies', BloodPressure:'Blood Pressure (Diastolic)', Insulin:'Insulin', Age:'Age' };
  let rows = '';
  if (model === 'disease') {
    const syms = inputs.symptoms || [];
    rows = `<tr><td>Symptoms Selected</td><td>${syms.map(s=>s.replace(/_/g,' ')).join(', ')}</td></tr>`;
  } else {
    Object.entries(inputs).forEach(([k,v]) => {
      if (!exclude.includes(k)) rows += `<tr><td>${labels[k]||k}</td><td>${v}</td></tr>`;
    });
  }
  tbody.innerHTML = rows;
}

// Recommendation Tabs
function initRecTabs() {
  document.querySelectorAll('.rec-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.rec-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.rec-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.panel).classList.add('active');
    });
  });
}

// Report Download
async function downloadReport(result) {
  const btn = document.getElementById('btn-report');
  btn.textContent = '⏳ Generating...';
  btn.disabled = true;
  const chartMainB64 = document.getElementById('chart-main')?.toDataURL('image/png');
  const chartPieB64  = document.getElementById('chart-pie')?.toDataURL('image/png');
  try {
    const res = await fetch('/report/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...result, chart_main: chartMainB64, chart_pie: chartPieB64 })
    });
    const data = await res.json();
    if (data.report_url) window.location.href = data.report_url;
  } catch (err) {
    alert('Report generation failed: ' + err.message);
  } finally {
    btn.textContent = '📄 Download Report';
    btn.disabled = false;
  }
}

// Helpers
function normalize(val, min, max) { return Math.min(1, Math.max(0, (parseFloat(val||0)-min)/(max-min))); }
function modelLabel(m) {
  return { diabetes:'Diabetes Predictor', heart:'Heart Disease Predictor', breast_cancer:'Breast Cancer Predictor', disease:'Disease Predictor' }[m] || m;
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  initCardAnimations();
  initSymptomSelector();
  initBMICompute();
  initHRCompute();
  initFormSubmit();
  initRecTabs();
  if (document.getElementById('result-banner')) initResultPage();
});
