# AI Intelligence Additions

This project now includes two new AI modules:

- Unsupervised learning for clustering + anomaly detection (`models/patient_clustering.py`)
- Reinforcement learning (simulation-based) for treatment strategy optimization (`models/treatment_rl_agent.py`)

These are intended for prototyping and dashboard visualizations. They are not certified for clinical use.

## Flask Endpoints (Python)

The Flask app exposes the following endpoints:

- `GET /api/docs` for a quick catalog of available Flask endpoints
- `POST /predict/cluster` for clustering + anomaly detection
- `POST /predict/treatment` for simulation-based RL treatment optimization
- `POST /predict/heart-risk` alias for `/predict/heart`
- `POST /predict/image` placeholder (no imaging model shipped)

### `/predict/cluster`

Example request:

```bash
curl -X POST http://localhost:8000/predict/cluster \
  -H "Content-Type: application/json" \
  -d '{
    "patients": [
      { "systolic": 120, "diastolic": 80, "glucose": 95 },
      { "systolic": 155, "diastolic": 100, "glucose": 210 }
    ],
    "features": ["systolic", "diastolic", "glucose"],
    "n_clusters": 3,
    "pca_components": 2,
    "dbscan_eps": 0.85,
    "dbscan_min_samples": 4
  }'
```

Response highlights:

- `projection`: 2D coordinates for scatter plots (`x`, `y`, `cluster`, `anomaly`)
- `anomalies`: list of flagged outliers (DBSCAN `-1` noise points)
- `cluster_profiles`: per-cluster mean feature values (for pattern summaries)

### `/predict/treatment`

Example request:

```bash
curl -X POST http://localhost:8000/predict/treatment \
  -H "Content-Type: application/json" \
  -d '{ "systolic": 142, "diastolic": 92, "glucose": 180, "age": 55 }'
```

Response highlights:

- `recommended_treatment`: abstract action chosen by the RL policy
- `expected_outcome_score`: simple score derived from expected next risk in simulation
- `risk_before` / `risk_after`: synthetic risk estimate in `[0, 1]`

## Next.js Dashboard Integration

The Next.js dashboard includes a new "AI Intelligence" section that calls two proxy routes:

- `GET /api/intelligence/cluster`
- `GET /api/intelligence/treatment`

These routes:

1. Require authentication and patient ownership checks
2. Pull vitals from Prisma
3. Call the Flask service (`/predict/cluster` and `/predict/treatment`)

### Configuration

Set this in `.env.local`:

```bash
AI_PYTHON_SERVICE_URL=http://localhost:8000
```

If `AI_PYTHON_SERVICE_URL` is not set, the proxy routes return a 501-style API error so the dashboard can fail gracefully.

