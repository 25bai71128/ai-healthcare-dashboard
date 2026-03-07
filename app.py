"""Flask application for production-style AI healthcare decision support."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, redirect, render_template, request, send_file, session, url_for

from jobs.task_queue import TaskQueue
from models.health_score_engine import calculate_health_score
from models.model_registry import (
    get_load_status,
    get_model_catalog,
    get_model_versions,
    load_models,
    predict_all,
    set_active_model_version,
)
from monitoring.drift_monitor import assess_prediction
from security.security_utils import (
    api_key_required,
    auth_required_enabled,
    authenticate_user,
    role_required,
    setup_security,
)
from storage.external_assets import sync_external_artifacts
from storage.prediction_store import PredictionStore, build_record

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
STATIC_CSS_DIR = STATIC_DIR / "css"
STATIC_JS_DIR = STATIC_DIR / "js"
TEMPLATES_DIR = BASE_DIR / "templates"

for folder in (
    MODELS_DIR,
    MODELS_DIR / "trained_models",
    MODELS_DIR / "metadata",
    DATA_DIR,
    REPORTS_DIR,
    LOGS_DIR,
    STATIC_DIR,
    STATIC_CSS_DIR,
    STATIC_JS_DIR,
    TEMPLATES_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("ai_healthcare_app")
PREDICTION_LOGGER = logging.getLogger("prediction_audit")
if not PREDICTION_LOGGER.handlers:
    file_handler = logging.FileHandler(LOGS_DIR / "predictions.log")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    PREDICTION_LOGGER.addHandler(file_handler)
    PREDICTION_LOGGER.setLevel(logging.INFO)

synced_artifacts = sync_external_artifacts(BASE_DIR, logger=LOGGER)
if synced_artifacts:
    LOGGER.info("External artifacts prepared: %s", ", ".join(synced_artifacts))

MODEL_LOAD_STATUS: dict[str, str] = {}
MODEL_REGISTRY_SIGNATURE: tuple[tuple[str, int], ...] = ()

PREDICTION_STORE = PredictionStore()
TASK_QUEUE = TaskQueue(workers=2)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-healthcare-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}

SECURITY_COMPONENTS = setup_security(app)
CSRF = SECURITY_COMPONENTS.get("csrf")


def _is_truthy(value: str | None, default: bool = False) -> bool:
    """Parse a boolean-like environment variable value."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _reports_enabled() -> bool:
    """Enable report generation outside Vercel unless overridden."""
    if "ENABLE_REPORTS" in os.environ:
        return _is_truthy(os.environ.get("ENABLE_REPORTS"), default=False)
    # Keep serverless cold start light by default on Vercel.
    return not _is_truthy(os.environ.get("VERCEL"), default=False)


@lru_cache(maxsize=1)
def _load_pyplot():
    """Load matplotlib lazily so API-only calls avoid heavy imports."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as pyplot
    except Exception as exc:  # pragma: no cover - depends on optional runtime extras
        raise RuntimeError("Matplotlib is not installed. Install requirements-optional.txt or disable reports.") from exc
    return pyplot


def _compute_registry_signature() -> tuple[tuple[str, int], ...]:
    """Build signature of model/metadata files to avoid unnecessary reloads."""
    tracked: list[tuple[str, int]] = []
    for folder in (MODELS_DIR / "trained_models", MODELS_DIR / "metadata"):
        for file in sorted(folder.glob("*")):
            if file.is_file():
                tracked.append((str(file.relative_to(BASE_DIR)), int(file.stat().st_mtime_ns)))
    return tuple(tracked)


def _maybe_reload_models(force: bool = False) -> None:
    """Reload model registry only when artifacts have changed."""
    global MODEL_LOAD_STATUS, MODEL_REGISTRY_SIGNATURE

    signature = _compute_registry_signature()
    if force or signature != MODEL_REGISTRY_SIGNATURE:
        MODEL_LOAD_STATUS = load_models()
        MODEL_REGISTRY_SIGNATURE = signature
        LOGGER.info("Model registry refreshed: %s", MODEL_LOAD_STATUS)


_maybe_reload_models(force=True)


@app.before_request
def _attach_request_id() -> None:
    """Attach request id for traceability."""
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def _set_request_id_header(response):
    """Expose request id in responses."""
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    return response


def _error_payload(code: str, message: str, status: int):
    """Build structured API error responses."""
    return jsonify({"ok": False, "error": {"code": code, "message": message, "request_id": g.request_id}}), status


def _parse_int(data: dict[str, Any], field_name: str, label: str, min_value: int, max_value: int) -> int:
    """Parse and validate integer inputs."""
    raw_value = str(data.get(field_name, "")).strip()
    if not raw_value:
        raise ValueError(f"{label} is required.")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number.") from exc

    if value < min_value or value > max_value:
        raise ValueError(f"{label} must be between {min_value} and {max_value}.")
    return value


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce JSON/form/query values to boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _validate_patient_input(payload: dict[str, Any]) -> dict[str, int]:
    """Validate normalized patient features."""
    return {
        "age": _parse_int(payload, "age", "Age", 1, 120),
        "blood_pressure": _parse_int(payload, "blood_pressure", "Blood Pressure", 50, 260),
        "cholesterol": _parse_int(payload, "cholesterol", "Cholesterol", 80, 500),
    }


def _recommendations(risk_level: str) -> list[str]:
    """Generate actionable recommendations by risk bucket."""
    if risk_level == "High":
        return [
            "Consult a physician for comprehensive cardiometabolic evaluation.",
            "Start strict blood pressure, glucose, and lipid monitoring.",
            "Adopt physician-guided exercise and nutrition plans immediately.",
        ]
    if risk_level == "Medium":
        return [
            "Reduce sodium and refined sugar intake with a structured diet plan.",
            "Increase weekly physical activity to at least 150 minutes.",
            "Repeat vitals and blood profile in 4-8 weeks.",
        ]
    return [
        "Maintain healthy nutrition, sleep quality, and hydration.",
        "Continue preventive exercise and stress-management routines.",
        "Follow annual wellness and preventive screening visits.",
    ]


def _top_driver_summary(model_predictions: dict[str, dict[str, Any]], limit: int = 3) -> list[str]:
    """Aggregate top contributing features across models for plain-language explanation."""
    scores: dict[str, float] = {}
    for payload in model_predictions.values():
        for feature in payload.get("top_features", []):
            name = str(feature.get("feature", ""))
            if not name:
                continue
            scores[name] = scores.get(name, 0.0) + float(feature.get("impact_percent", 0.0))

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [f"{feature.replace('_', ' ').title()} ({round(score, 1)} impact)" for feature, score in ranked]


def _build_result_explanation(
    patient_data: dict[str, int],
    model_predictions: dict[str, dict[str, Any]],
    health_score: dict[str, Any],
    monitoring: dict[str, Any],
) -> dict[str, Any]:
    """Create concise interpretation text for the dashboard and report."""
    risk_level = health_score["risk_level"]
    score = health_score["overall_health_score"]
    drivers = _top_driver_summary(model_predictions)

    if risk_level == "High":
        meaning = "Your current indicators suggest a high near-term risk profile."
    elif risk_level == "Medium":
        meaning = "Your indicators show moderate risk and early intervention can help significantly."
    else:
        meaning = "Your indicators are currently in a lower-risk zone, but prevention remains important."

    if monitoring.get("high_model_disagreement"):
        confidence = "Model disagreement is elevated, so this estimate should be interpreted cautiously."
    else:
        confidence = "Model agreement is consistent for this estimate."

    summary = (
        f"Health score is {score}% ({risk_level} risk). {meaning} "
        f"Primary risk drivers identified by the models: {', '.join(drivers) if drivers else 'not available'}."
    )

    return {
        "summary": summary,
        "meaning": meaning,
        "drivers": drivers,
        "confidence_note": confidence,
        "patient_snapshot": {
            "age": patient_data["age"],
            "blood_pressure": patient_data["blood_pressure"],
            "cholesterol": patient_data["cholesterol"],
        },
    }


def _build_precautions(patient_data: dict[str, int], health_score: dict[str, Any]) -> list[dict[str, str]]:
    """Generate personalized preventive precautions."""
    precautions: list[dict[str, str]] = []

    if patient_data["blood_pressure"] >= 140:
        precautions.append(
            {
                "title": "Control Blood Pressure",
                "action": "Track blood pressure daily, reduce sodium intake, and follow clinician guidance on BP management.",
                "priority": "High",
            }
        )

    if patient_data["cholesterol"] >= 240:
        precautions.append(
            {
                "title": "Improve Lipid Profile",
                "action": "Limit fried/processed foods, increase fiber intake, and schedule lipid panel follow-up in 4-8 weeks.",
                "priority": "High",
            }
        )

    if patient_data["age"] >= 50:
        precautions.append(
            {
                "title": "Increase Preventive Screening",
                "action": "Plan regular metabolic and cardiovascular checkups with your healthcare provider.",
                "priority": "Medium",
            }
        )

    if health_score["risk_level"] == "High":
        precautions.append(
            {
                "title": "Clinical Consultation",
                "action": "Book a physician consultation soon for full diagnostic evaluation and treatment planning.",
                "priority": "High",
            }
        )
    elif health_score["risk_level"] == "Medium":
        precautions.append(
            {
                "title": "Lifestyle Correction Plan",
                "action": "Adopt a structured exercise and nutrition routine and re-evaluate risk in 1-2 months.",
                "priority": "Medium",
            }
        )
    else:
        precautions.append(
            {
                "title": "Maintain Current Progress",
                "action": "Continue preventive habits and repeat health screening at regular intervals.",
                "priority": "Low",
            }
        )

    precautions.append(
        {
            "title": "Sleep and Stress Hygiene",
            "action": "Aim for 7-8 hours of sleep, daily hydration, and stress control practices such as walking or breathing exercises.",
            "priority": "Medium",
        }
    )

    return precautions


def _build_alert_rules(
    patient_data: dict[str, int],
    health_score: dict[str, Any],
    monitoring: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate actionable system alerts for risk, drift, and disagreement."""
    alerts: list[dict[str, str]] = []

    if health_score["risk_level"] == "High":
        alerts.append(
            {
                "type": "high_risk",
                "severity": "danger",
                "title": "High Risk Alert",
                "message": "Global health score is high. Prioritize clinician review and intervention.",
            }
        )

    if monitoring.get("drift_detected"):
        alerts.append(
            {
                "type": "data_drift",
                "severity": "warning",
                "title": "Data Drift Alert",
                "message": "Patient indicators are outside baseline distribution. Re-validate context before decisions.",
            }
        )

    if monitoring.get("high_model_disagreement"):
        alerts.append(
            {
                "type": "model_disagreement",
                "severity": "warning",
                "title": "Model Disagreement Alert",
                "message": "Model outputs diverge significantly. Consider additional clinical evidence.",
            }
        )

    if patient_data["blood_pressure"] >= 160:
        alerts.append(
            {
                "type": "bp_critical",
                "severity": "danger",
                "title": "Critical Blood Pressure",
                "message": "Blood pressure is in a high range and needs immediate evaluation.",
            }
        )

    if patient_data["cholesterol"] >= 260:
        alerts.append(
            {
                "type": "cholesterol_critical",
                "severity": "warning",
                "title": "High Cholesterol",
                "message": "Cholesterol is significantly elevated. Early lipid management is strongly recommended.",
            }
        )

    return alerts


def _aggregate_feature_impacts(model_predictions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate top-feature impacts across models for visualization/reporting."""
    impact_map: dict[str, float] = {}
    for payload in model_predictions.values():
        for feature in payload.get("top_features", []):
            name = str(feature.get("feature", "")).strip()
            if not name:
                continue
            impact_map[name] = impact_map.get(name, 0.0) + float(feature.get("impact_percent", 0.0))

    ranked = sorted(impact_map.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "feature": name,
            "impact_percent": round(value, 2),
            "label": name.replace("_", " ").title(),
        }
        for name, value in ranked
    ]


def _atomic_save_figure(fig: Any, out_file: Path, dpi: int = 140) -> str:
    """Write figure files atomically."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=out_file.parent)
    try:
        fig.tight_layout()
        fig.savefig(tmp.name, dpi=dpi)
        os.replace(tmp.name, out_file)
        return str(out_file)
    finally:
        pyplot = _load_pyplot()
        tmp.close()
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        pyplot.close(fig)


def _generate_patient_chart(patient_data: dict[str, int]) -> str:
    """Generate patient indicator chart for reports."""
    pyplot = _load_pyplot()
    labels = ["Age", "Blood Pressure", "Cholesterol"]
    values = [patient_data["age"], patient_data["blood_pressure"], patient_data["cholesterol"]]

    fig, ax = pyplot.subplots(figsize=(6.5, 3.8))
    ax.bar(labels, values, color=["#2563eb", "#10b981", "#f59e0b"])
    ax.set_title("Patient Indicators")
    ax.set_ylabel("Value")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    return _atomic_save_figure(fig, STATIC_DIR / "chart.png")


def _generate_prediction_comparison_chart(model_predictions: dict[str, dict[str, Any]]) -> str:
    """Generate model comparison chart for reports."""
    pyplot = _load_pyplot()
    labels = [entry["metadata"]["model_name"] for entry in model_predictions.values()]
    values = [entry["risk_percent"] for entry in model_predictions.values()]

    fig, ax = pyplot.subplots(figsize=(7.2, 4.0))
    ax.barh(labels, values, color="#2563eb")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Risk %")
    ax.set_title("Model Prediction Comparison")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    return _atomic_save_figure(fig, STATIC_DIR / "comparison_chart.png")


def _generate_risk_breakdown_chart(health_score: dict[str, Any]) -> str:
    """Generate risk breakdown pie chart for reports."""
    pyplot = _load_pyplot()
    risk = float(health_score["overall_health_score"])
    safe_margin = max(0.0, 100.0 - risk)

    fig, ax = pyplot.subplots(figsize=(4.6, 4.6))
    ax.pie(
        [risk, safe_margin],
        labels=["Risk", "Healthy Margin"],
        autopct="%1.1f%%",
        colors=["#ef4444", "#10b981"],
    )
    ax.set_title("Unified Risk Breakdown")
    return _atomic_save_figure(fig, STATIC_DIR / "risk_breakdown.png")


def _generate_feature_impact_chart(feature_impacts: list[dict[str, Any]]) -> str:
    """Generate feature impact summary chart for reports."""
    pyplot = _load_pyplot()
    labels = [item["label"] for item in feature_impacts[:6]] or ["No Data"]
    values = [item["impact_percent"] for item in feature_impacts[:6]] or [0.0]
    colors = ["#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"][: len(labels)]

    fig, ax = pyplot.subplots(figsize=(7.2, 3.8))
    ax.barh(labels, values, color=colors)
    ax.set_xlabel("Cumulative Impact %")
    ax.set_title("Top Feature Impact Summary")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    return _atomic_save_figure(fig, STATIC_DIR / "feature_impact_chart.png")


def _generate_model_weight_risk_chart(model_predictions: dict[str, dict[str, Any]]) -> str:
    """Generate scatter visualization for model weight vs risk contribution."""
    pyplot = _load_pyplot()
    names = [entry["metadata"]["model_name"] for entry in model_predictions.values()]
    weights = [float(entry.get("weight", 0.0)) for entry in model_predictions.values()]
    risks = [float(entry.get("risk_percent", 0.0)) for entry in model_predictions.values()]
    sizes = [max(120, weight * 800) for weight in weights]

    fig, ax = pyplot.subplots(figsize=(7.2, 4.0))
    scatter = ax.scatter(weights, risks, s=sizes, c=risks, cmap="RdYlGn_r", alpha=0.8, edgecolors="#1f2937")
    for idx, name in enumerate(names):
        ax.annotate(name, (weights[idx], risks[idx]), xytext=(4, 4), textcoords="offset points", fontsize=8)

    ax.set_xlabel("Model Weight")
    ax.set_ylabel("Risk %")
    ax.set_title("Model Weight vs Risk")
    ax.grid(linestyle="--", alpha=0.3)
    fig.colorbar(scatter, ax=ax, label="Risk %")
    return _atomic_save_figure(fig, STATIC_DIR / "model_weight_risk_chart.png")


def _generate_history_trend_chart(history_rows: list[dict[str, Any]]) -> str:
    """Generate historical trend chart from persisted predictions."""
    pyplot = _load_pyplot()
    recent = list(reversed(history_rows[-20:]))
    if not recent:
        recent = [{"created_at": "n/a", "health_score": {"overall_health_score": 0.0}}]

    labels = [str(row.get("created_at", ""))[5:16].replace("T", " ") for row in recent]
    scores = [float(row.get("health_score", {}).get("overall_health_score", 0.0)) for row in recent]
    x_points = list(range(len(scores)))

    fig, ax = pyplot.subplots(figsize=(7.2, 3.8))
    ax.plot(x_points, scores, marker="o", color="#2563eb", linewidth=2)
    ax.fill_between(x_points, scores, alpha=0.15, color="#2563eb")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Health Score %")
    ax.set_title("Recent Health Score Trend")
    ax.grid(linestyle="--", alpha=0.3)
    ax.set_xticks(x_points)
    ax.set_xticklabels(labels)
    ax.tick_params(axis="x", labelrotation=35, labelsize=8)
    return _atomic_save_figure(fig, STATIC_DIR / "history_trend_chart.png")


def _persist_prediction(
    result: dict[str, Any],
    request_id: str,
) -> None:
    """Persist prediction to durable storage and audit logs."""
    record = build_record(
        request_id=request_id,
        patient_data=result["patient_data"],
        model_predictions=result["model_predictions"],
        health_score=result["health_score"],
        monitoring=result["monitoring"],
        report_file=result["report_file"],
    )
    PREDICTION_STORE.save_prediction(record)

    log_payload = {
        "request_id": request_id,
        "patient_input": result["patient_data"],
        "model_outputs": {
            key: {
                "risk_percent": value["risk_percent"],
                "version": value["version"],
                "weight": value["weight"],
            }
            for key, value in result["model_predictions"].items()
        },
        "health_score": result["health_score"],
        "monitoring": result["monitoring"],
        "alerts": result.get("alerts", []),
    }
    PREDICTION_LOGGER.info(json.dumps(log_payload, separators=(",", ":")))


def _run_integrated_prediction(
    payload: dict[str, Any],
    request_id: str | None = None,
    persist: bool = True,
    build_report: bool | None = None,
) -> dict[str, Any]:
    """Execute integrated scoring, optional reporting, and optional persistence."""
    request_id = request_id or str(uuid.uuid4())
    if build_report is None:
        build_report = _reports_enabled()
    _maybe_reload_models(force=False)

    patient_data = _validate_patient_input(payload)
    model_predictions = predict_all(patient_data)

    health_score = calculate_health_score(model_predictions)
    monitoring = assess_prediction(patient_data, model_predictions, health_score)
    alerts = _build_alert_rules(patient_data, health_score, monitoring)
    feature_impacts = _aggregate_feature_impacts(model_predictions)
    result_explanation = _build_result_explanation(patient_data, model_predictions, health_score, monitoring)
    precautions = _build_precautions(patient_data, health_score)
    recommendations = _recommendations(health_score["risk_level"])

    report_file = ""
    report_error = ""
    if build_report:
        try:
            # Report stack is optional for serverless deployments.
            from models.report_generator import generate_report

            history_rows = PREDICTION_STORE.fetch_recent(limit=30)
            chart_paths = {
                "patient_chart": _generate_patient_chart(patient_data),
                "comparison_chart": _generate_prediction_comparison_chart(model_predictions),
                "risk_breakdown_chart": _generate_risk_breakdown_chart(health_score),
                "feature_impact_chart": _generate_feature_impact_chart(feature_impacts),
                "model_weight_risk_chart": _generate_model_weight_risk_chart(model_predictions),
                "history_trend_chart": _generate_history_trend_chart(history_rows),
            }
            report_path = generate_report(
                patient_data=patient_data,
                health_score=health_score,
                model_predictions=model_predictions,
                result_explanation=result_explanation,
                precautions=precautions,
                recommendations=recommendations,
                monitoring=monitoring,
                alerts=alerts,
                feature_impacts=feature_impacts,
                chart_paths=chart_paths,
            )
            report_file = Path(report_path).name
        except Exception as exc:  # pragma: no cover - defensive fallback for optional dependencies
            report_error = str(exc)
            LOGGER.warning("Report generation skipped: %s", exc)

    result = {
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "patient_data": patient_data,
        "model_predictions": model_predictions,
        "health_score": health_score,
        "monitoring": monitoring,
        "alerts": alerts,
        "feature_impacts": feature_impacts,
        "result_explanation": result_explanation,
        "precautions": precautions,
        "recommendations": recommendations,
        "report_file": report_file,
        "reporting": {
            "enabled": build_report,
            "error": report_error,
        },
        "model_loading_status": MODEL_LOAD_STATUS,
        "model_versions": get_model_versions(),
    }

    if persist:
        _persist_prediction(result, request_id=request_id)
    return result


@app.route("/")
def index():
    """Render input page with model registry diagnostics."""
    return render_template(
        "index.html",
        loading_status=MODEL_LOAD_STATUS,
        auth_enabled=auth_required_enabled(),
        current_user=session.get("username"),
        current_role=session.get("role"),
    )


@app.route("/login", methods=["POST"])
def login():
    """Authenticate user for optional role-protected mode."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    profile = authenticate_user(username, password)
    if not profile:
        if request.is_json:
            return _error_payload("AUTH_INVALID", "Invalid credentials", 401)
        return render_template("index.html", error="Invalid credentials", loading_status=MODEL_LOAD_STATUS), 401

    session["username"] = profile["username"]
    session["role"] = profile["role"]

    if request.is_json:
        return jsonify({"ok": True, "user": profile}), 200
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    """End user session."""
    session.clear()
    return redirect(url_for("index"))


@app.route("/predict", methods=["POST"])
@role_required({"admin", "analyst"})
def predict():
    """Form endpoint for synchronous integrated prediction."""
    try:
        result = _run_integrated_prediction(
            request.form.to_dict(),
            request_id=g.request_id,
            build_report=_reports_enabled(),
        )
        session["latest_result"] = result
        return redirect(url_for("dashboard"))
    except ValueError as exc:
        LOGGER.warning("Validation error: %s", exc)
        return render_template(
            "index.html",
            error=str(exc),
            values=request.form,
            loading_status=MODEL_LOAD_STATUS,
            auth_enabled=auth_required_enabled(),
            current_user=session.get("username"),
            current_role=session.get("role"),
        ), 400
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Prediction pipeline failed")
        return render_template(
            "index.html",
            error=f"Prediction failed: {exc}",
            values=request.form,
            loading_status=MODEL_LOAD_STATUS,
            auth_enabled=auth_required_enabled(),
            current_user=session.get("username"),
            current_role=session.get("role"),
        ), 500


@app.route("/dashboard")
@role_required({"admin", "analyst"})
def dashboard():
    """Render patient analytics dashboard."""
    history_records = PREDICTION_STORE.fetch_recent(limit=40)
    model_catalog = get_model_catalog()
    monitoring_summary = PREDICTION_STORE.monitoring_summary()
    return render_template(
        "dashboard.html",
        result=session.get("latest_result"),
        loading_status=MODEL_LOAD_STATUS,
        auth_enabled=auth_required_enabled(),
        current_user=session.get("username"),
        current_role=session.get("role"),
        history_records=history_records,
        model_catalog=model_catalog,
        monitoring_summary=monitoring_summary,
    )


@app.route("/api/predict", methods=["POST"])
@api_key_required
@role_required({"admin", "analyst"})
def api_predict():
    """API endpoint for synchronous or asynchronous prediction."""
    payload = request.get_json(silent=True) or {}

    async_flag = _coerce_bool(payload.pop("async", None)) or _coerce_bool(request.args.get("async"), default=False)
    build_report = _coerce_bool(payload.pop("build_report", None)) or _coerce_bool(
        request.args.get("build_report"),
        default=False,
    )
    if async_flag:
        job_id = TASK_QUEUE.submit(_run_integrated_prediction, payload, g.request_id, True, build_report)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "request_id": g.request_id,
                "status_url": url_for("api_job_status", job_id=job_id, _external=False),
            }
        ), 202

    try:
        result = _run_integrated_prediction(payload, request_id=g.request_id, build_report=build_report)
        session["latest_result"] = result
        return jsonify({"ok": True, "data": result, "request_id": g.request_id}), 200
    except ValueError as exc:
        LOGGER.warning("API validation error: %s", exc)
        return _error_payload("VALIDATION_ERROR", str(exc), 400)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("API prediction failed")
        return _error_payload("PREDICTION_FAILED", str(exc), 500)


@app.route("/api/whatif", methods=["POST"])
@api_key_required
@role_required({"admin", "analyst"})
def api_whatif():
    """Low-latency what-if simulation without persistence or PDF generation."""
    payload = request.get_json(silent=True) or {}
    try:
        result = _run_integrated_prediction(
            payload,
            request_id=g.request_id,
            persist=False,
            build_report=False,
        )
        return jsonify({"ok": True, "data": result, "request_id": g.request_id}), 200
    except ValueError as exc:
        LOGGER.warning("What-if validation error: %s", exc)
        return _error_payload("VALIDATION_ERROR", str(exc), 400)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("What-if simulation failed")
        return _error_payload("WHATIF_FAILED", str(exc), 500)


@app.route("/api/jobs/<job_id>", methods=["GET"])
@api_key_required
@role_required({"admin", "analyst"})
def api_job_status(job_id: str):
    """Get async background job status."""
    payload = TASK_QUEUE.get(job_id)
    if payload is None:
        return _error_payload("JOB_NOT_FOUND", f"No job with id {job_id}", 404)
    return jsonify({"ok": True, "job": payload, "request_id": g.request_id}), 200


@app.route("/api/models", methods=["GET"])
@api_key_required
@role_required({"admin", "analyst"})
def api_models():
    """Return model catalog, versions, and loading status."""
    return jsonify(
        {
            "ok": True,
            "data": {
                "status": get_load_status(),
                "versions": get_model_versions(),
                "catalog": get_model_catalog(),
            },
            "request_id": g.request_id,
        }
    ), 200


@app.route("/api/models/activate", methods=["POST"])
@api_key_required
@role_required({"admin"})
def api_activate_model():
    """Activate a model version to support rollback/roll-forward operations."""
    payload = request.get_json(silent=True) or {}
    family = str(payload.get("family", "")).strip()
    version = str(payload.get("version", "")).strip()
    if not family or not version:
        return _error_payload("ACTIVATE_INVALID", "Both family and version are required", 400)

    success = set_active_model_version(family, version)
    if not success:
        return _error_payload("ACTIVATE_FAILED", "Unknown family/version", 404)

    return jsonify({"ok": True, "message": "Active model version updated", "request_id": g.request_id}), 200


@app.route("/api/history", methods=["GET"])
@api_key_required
@role_required({"admin", "analyst"})
def api_history():
    """Return recent persisted predictions from storage."""
    limit = int(request.args.get("limit", 25))
    records = PREDICTION_STORE.fetch_recent(limit=max(1, min(limit, 200)))
    return jsonify({"ok": True, "data": records, "request_id": g.request_id}), 200


@app.route("/api/cases/<request_id>/notes", methods=["GET"])
@api_key_required
@role_required({"admin", "analyst"})
def api_case_notes(request_id: str):
    """Fetch clinician notes and tags for a prediction case."""
    notes = PREDICTION_STORE.fetch_case_notes(request_id=request_id, limit=50)
    return jsonify({"ok": True, "data": notes, "request_id": g.request_id}), 200


@app.route("/api/cases/annotate", methods=["POST"])
@api_key_required
@role_required({"admin", "analyst"})
def api_case_annotate():
    """Attach clinician note and tags to a prediction case."""
    payload = request.get_json(silent=True) or {}
    request_id = str(payload.get("request_id", "")).strip()
    note = str(payload.get("note", "")).strip()
    tags_payload = payload.get("tags", [])

    if not request_id:
        return _error_payload("NOTE_INVALID", "request_id is required", 400)
    if not note:
        return _error_payload("NOTE_INVALID", "note is required", 400)

    tags: list[str]
    if isinstance(tags_payload, str):
        tags = [item.strip() for item in tags_payload.split(",") if item.strip()]
    elif isinstance(tags_payload, list):
        tags = [str(item).strip() for item in tags_payload if str(item).strip()]
    else:
        tags = []

    author = session.get("username") or "system"
    PREDICTION_STORE.save_case_note(request_id=request_id, author=str(author), note=note, tags=tags)
    notes = PREDICTION_STORE.fetch_case_notes(request_id=request_id, limit=50)
    return jsonify({"ok": True, "data": notes, "request_id": g.request_id}), 200


@app.route("/api/monitoring", methods=["GET"])
@api_key_required
@role_required({"admin", "analyst"})
def api_monitoring():
    """Return drift and quality monitoring summary."""
    summary = PREDICTION_STORE.monitoring_summary()
    return jsonify({"ok": True, "data": summary, "request_id": g.request_id}), 200


@app.route("/api/health", methods=["GET"])
def api_health():
    """Simple healthcheck endpoint."""
    return jsonify({"ok": True, "service": "ai-healthcare-platform", "request_id": g.request_id}), 200


@app.route("/api/openapi.json", methods=["GET"])
def api_openapi():
    """Return minimal OpenAPI contract for integration clients."""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "AI Healthcare Decision Support API",
            "version": "1.0.0",
        },
        "paths": {
            "/api/predict": {"post": {"summary": "Predict health risk"}},
            "/api/whatif": {"post": {"summary": "Live what-if simulation"}},
            "/api/jobs/{job_id}": {"get": {"summary": "Get async job status"}},
            "/api/models": {"get": {"summary": "Get model registry catalog"}},
            "/api/models/activate": {"post": {"summary": "Activate specific model version"}},
            "/api/history": {"get": {"summary": "Get recent prediction history"}},
            "/api/cases/{request_id}/notes": {"get": {"summary": "Get clinician notes for a case"}},
            "/api/cases/annotate": {"post": {"summary": "Add clinician note/tags to a case"}},
            "/api/monitoring": {"get": {"summary": "Get drift/quality summary"}},
            "/api/health": {"get": {"summary": "Service health check"}},
        },
    }
    return jsonify(spec), 200


@app.route("/download")
@role_required({"admin", "analyst"})
def download():
    """Download report file from reports directory."""
    report_name = request.args.get("report", "").strip()
    if report_name:
        report_path = (REPORTS_DIR / report_name).resolve()
        if REPORTS_DIR.resolve() not in report_path.parents:
            return "Invalid report path.", 400
    else:
        reports = sorted(REPORTS_DIR.glob("health_report_*.pdf"))
        if not reports:
            return "No report has been generated yet.", 404
        report_path = reports[-1]

    if not report_path.exists():
        return "Requested report was not found.", 404
    return send_file(report_path, as_attachment=True)


# Exempt JSON API endpoints from CSRF when extension is available.
if CSRF is not None:
    CSRF.exempt(api_predict)
    CSRF.exempt(api_whatif)
    CSRF.exempt(api_activate_model)
    CSRF.exempt(api_models)
    CSRF.exempt(api_history)
    CSRF.exempt(api_case_notes)
    CSRF.exempt(api_case_annotate)
    CSRF.exempt(api_monitoring)
    CSRF.exempt(api_health)
    CSRF.exempt(api_openapi)
    CSRF.exempt(api_job_status)
    CSRF.exempt(login)


if __name__ == "__main__":
    app.run(debug=True)
