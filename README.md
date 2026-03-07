# AI Healthcare Decision Support Dashboard

> **Note:** This project is a demonstration prototype of an AI-driven healthcare decision support platform. It is **not** certified for clinical use.

## 🧠 Project Overview

AI Healthcare Dashboard is a Python/Flask application that combines multiple risk models to generate a unified health risk score, explainability insights, and a downloadable PDF report. It includes:

- Multi-model scoring with active versioning and model rollout support
- Real-time “what‑if” simulation API
- Drift and disagreement monitoring
- PDF report generation including charts and model explainability
- Lightweight task queue for asynchronous jobs
- Optional persistence via SQLite (default) or PostgreSQL
- Optional session auth and API key enforcement

---

## Next.js Healthcare Dashboard (Overhaul)

This repository now also includes a full **Next.js App Router** dashboard layer with:

- Critical Alerts panel (upcoming appointments, overdue medications, abnormal vitals)
- Context-aware AI assistant with medical safety filters and critical advice disclaimer
- Protected CRUD API routes for appointments, medications, vitals, and lab results
- PostgreSQL/Supabase integration via Prisma
- JWT auth with NextAuth credentials provider (email/password)
- Encrypted sensitive DB fields (AES-256-GCM)
- Responsive analytics charts and longitudinal timeline
- React Query state management + polling for near real-time updates

### Next.js Quick Start

1. Install dependencies:

```bash
npm install
```

2. Configure environment:

```bash
cp .env.example .env.local
```

Set at minimum:

- `DATABASE_URL` (PostgreSQL/Supabase connection)
- `NEXTAUTH_SECRET`
- `NEXTAUTH_URL` (typically `http://localhost:3000`)
- `FIELD_ENCRYPTION_KEY` (base64 32-byte key)

3. Generate Prisma client + migrate + seed:

```bash
npm run prisma:generate
npm run prisma:migrate -- --name init_dashboard
npm run prisma:seed
```

4. Start the Next.js dashboard:

```bash
npm run dev
```

5. Open:

`http://localhost:3000/login`

Use the seed credentials from `.env.local`:

- `SEED_USER_EMAIL`
- `SEED_USER_PASSWORD`

### API Surface (Next.js)

- `GET/POST /api/appointments`
- `GET/PATCH/DELETE /api/appointments/:id`
- `GET/POST /api/medications`
- `GET/PATCH/DELETE /api/medications/:id`
- `GET/POST /api/vitals`
- `GET/PATCH/DELETE /api/vitals/:id`
- `GET/POST /api/labs`
- `GET/PATCH/DELETE /api/labs/:id`
- `GET /api/alerts`
- `GET /api/analytics`
- `GET /api/timeline`
- `POST /api/assistant`
- `GET /api/profile`

All patient-data routes require authentication and ownership checks.

---

## 🚀 Features

- **Multi‑model ensemble scoring** using a model registry (`models/model_registry.py`) with version control
- **Explainability**: per‑model top feature contributions using SHAP or feature importance
- **Risk scoring engine** combining model outputs into a single health score (`models/health_score_engine.py`)
- **Monitoring** for data drift and model disagreement (`monitoring/drift_monitor.py`)
- **Audit logging** and prediction history storage (`storage/prediction_store.py`)
- **PDF report generation** with charts (`models/report_generator.py`)
- **Interactive UI** with a dashboard, charting, and clinician note capture
- **API endpoints** for prediction, jobs, model activation, history, and monitoring
- **Docker support** for local development and deployment

---

## 🧩 Installation

### Prerequisites

- Python 3.12+ (recommended)
- pip
- (Optional) Docker + Docker Compose for containerized deployment

### Local development (venv)

```bash
git clone https://github.com/25bai71128/ai-healthcare-dashboard.git
cd ai-healthcare-dashboard
python -m venv .venv
source .venv/bin/activate
# Full development dependencies (includes model training + reports)
pip install -r requirements-dev.txt
```

> **Note:** `requirements.txt` is intentionally slimmed for AWS Lambda deployments (keeps the dependency bundle < 500MB). If you need full ML/reporting features locally, install from `requirements-dev.txt`.

### Run locally

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
python -m flask run --port 8000
```

Then open: http://localhost:8000

### Run with Docker

```bash
docker compose up --build
```

The app will be available at: http://localhost:8000

---

## ▶️ Usage Examples

### Web UI

- Visit `/` to submit patient inputs (age, bp, cholesterol) and generate a report.
- Visit `/dashboard` to view the prediction dashboard and manage model versions.

### API

#### Predict (synchronous)

```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"age": 45, "blood_pressure": 138, "cholesterol": 210}'
```

#### What‑if (no persistence)

```bash
curl -X POST http://localhost:8000/api/whatif \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"age": 45, "blood_pressure": 138, "cholesterol": 210}'
```

#### Activate a model version

```bash
curl -X POST http://localhost:8000/api/models/activate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"family": "diabetes", "version": "1.0.0"}'
```

#### Get prediction history

```bash
curl -X GET "http://localhost:8000/api/history?limit=10" \
  -H "X-API-Key: $API_KEY"
```

---

## 🧰 Project Structure

```
app.py               # Flask entrypoint + API routes
models/              # Model loading, scoring, reporting
  model_registry.py  # Dynamic model registry & versioning
  health_score_engine.py
  report_generator.py
  health_model.py    # training utilities
  trained_models/    # Pickled .pkl models
storage/             # Prediction persistence (SQLite/PostgreSQL)
monitoring/          # Drift / disagreement probing
security/            # Auth, API key check, rate limiting
templates/           # Jinja2 HTML UI templates
static/              # JS/CSS and dashboard assets
```

---

## 🔧 Configuration & Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FLASK_SECRET_KEY` | Flask session secret | `dev-healthcare-secret-key` |
| `AUTH_REQUIRED` | Enable session-based auth (true/false) | `false` |
| `ADMIN_USER` | Admin username | `admin` |
| `ADMIN_PASSWORD` | Admin password | `admin123` |
| `ANALYST_USER` | Analyst username | `analyst` |
| `ANALYST_PASSWORD` | Analyst password | `analyst123` |
| `API_KEY` | API key for /api endpoints | (empty = disabled) |
| `DATABASE_URL` | Postgres URL (optional) | (SQLite fallback) |
| `SESSION_COOKIE_SECURE` | Secure session cookie (true/false) | `false` |

> Tip: Use a `.env` file (shown in `.env.example`) in development.

---

## 🧪 Testing

A small suite of unit tests exists under `tests/`, including:

- `tests/test_app.py` (API integration)
- `tests/test_health_score_engine.py` (score aggregation logic)
- `tests/test_drift_monitor.py` (drift detection logic)
- `tests/test_model_registry.py` (model registry bootstrapping)

Run tests with:

```bash
pytest -q
```

---

## 🤝 Contributing

Contributions are welcome! Here are recommended steps:

1. Fork the repository and create a feature branch.
2. Install dependencies in a venv and run the app locally.
3. Add/extend tests in `tests/`.
4. Update documentation and changelog as needed.
5. Submit a pull request with a clear summary and any relevant screenshots.

Please follow common Python best practices:

- Use `black` / `ruff` / `isort` for formatting (not included but recommended).
- Keep business logic in `models/` and keep `app.py` focused on routing.

---

## 📄 License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for full text.

---

## 💡 Notes

- Models are auto‑bootstraped using `data/health_data.csv` when the `models/trained_models/` directory is empty.
- If SHAP is not installed or fails to build an explainer, the system falls back to feature importances.
- Reports are generated to `reports/` and can be downloaded via the UI or `/download` endpoint.
