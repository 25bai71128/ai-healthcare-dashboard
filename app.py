from __future__ import annotations

import base64
import io
import logging
import os
import pickle
import tempfile
import uuid
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

MPL_CONFIG_DIR = Path(__file__).resolve().parent / ".matplotlib"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib
import numpy as np
from joblib import load as joblib_load
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models.medical_ai_guardrails import (
    ConfidenceCalibrator,
    DataQualityTracker,
    ExplainabilityModule,
    MedicalInputValidator,
    ModelMetricsProvider,
    ResultMessageGenerator,
)
from models.patient_clustering import cluster_patients
from models.treatment_rl_agent import get_default_agent
from recommendations import RECOMMENDATIONS

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Optional import for model compatibility. We do not fail if unavailable.
try:  # pragma: no cover
    import xgboost  # noqa: F401
except Exception:  # pragma: no cover
    xgboost = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("mediai")

BASE_DIR = Path(__file__).resolve().parent
MODELS_ROOT = BASE_DIR / "models"
MODEL_SEARCH_DIRS = [MODELS_ROOT / "trained_models", MODELS_ROOT]
ALLOWED_MODELS = {"disease", "breast_cancer", "diabetes", "heart"}
DIABETES_FEATURES = [
    "Pregnancies",
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
    "DiabetesPedigreeFunction",
    "Age",
]
HEART_FEATURES = [
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
]
DIABETES_ENGINEERED_FEATURES = [
    "Pregnancies",
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
    "DiabetesPedigreeFunction",
    "Age",
    "BMI_Age",
    "Glucose_BMI",
    "Age_Group",
]
HEART_NUMERIC_FEATURES = ["age", "trestbps", "chol", "thalach", "oldpeak"]
HEART_CATEGORICAL_FEATURES = {
    "sex": [0, 1],
    "cp": [0, 1, 2, 3],
    "fbs": [0, 1],
    "restecg": [0, 1, 2],
    "exang": [0, 1],
    "slope": [0, 1, 2],
    "ca": [0, 1, 2, 3, 4],
    "thal": [1, 2, 3],
}
MODEL_DESCRIPTIONS = {
    "disease": "Select symptoms and predict the most likely condition from the trained classifier.",
    "breast_cancer": "Enter tumor feature measurements to classify risk as benign or malignant.",
    "diabetes": "Provide lifestyle and clinical inputs to estimate diabetes risk.",
    "heart": "Use demographic and cardiology indicators to assess heart disease risk.",
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "mediai-dev-key")
CORS(app)


MODELS: dict[str, Any] = {
    "disease_model": None,
    "disease_label_encoder": None,
    "disease_feature_names": [],
    "breast_cancer_mlp": None,
    "breast_cancer_scaler": None,
    "breast_cancer_features": [],
    "diabetes_model": None,
    "diabetes_scaler": None,
    "heart_disease_model": None,
}

CONFIDENCE_CALIBRATOR = ConfidenceCalibrator()
INPUT_VALIDATOR = MedicalInputValidator()
DATA_QUALITY_TRACKER = DataQualityTracker()
EXPLAINABILITY = ExplainabilityModule()
METRICS_PROVIDER: ModelMetricsProvider | None = None
MESSAGE_GENERATOR: ResultMessageGenerator | None = None


BREAST_TOOLTIPS = {
    "radius_mean": "Typical range: 6 to 30",
    "texture_mean": "Typical range: 9 to 40",
    "perimeter_mean": "Typical range: 40 to 200",
    "area_mean": "Typical range: 140 to 2600",
    "smoothness_mean": "Typical range: 0.05 to 0.16",
    "compactness_mean": "Typical range: 0.02 to 0.35",
    "concavity_mean": "Typical range: 0.00 to 0.45",
    "concave points_mean": "Typical range: 0.00 to 0.20",
    "symmetry_mean": "Typical range: 0.10 to 0.35",
    "fractal_dimension_mean": "Typical range: 0.05 to 0.10",
}


def _load_pickle(path: Path, label: str) -> Any:
    if not path.exists():
        LOGGER.error("Missing model file: %s", path)
        return None
    try:
        with path.open("rb") as file:
            obj = pickle.load(file)
        LOGGER.info("Loaded %s", label)
        return obj
    except Exception as exc:
        LOGGER.warning("pickle.load failed for %s (%s). Trying joblib.load...", label, exc)
        try:
            obj = joblib_load(path)
            LOGGER.info("Loaded %s via joblib", label)
            return obj
        except Exception as joblib_exc:
            LOGGER.exception("Failed to load %s: %s", label, joblib_exc)
            return None


def _resolve_model_path(*file_names: str) -> Path | None:
    tried: list[str] = []
    for model_dir in MODEL_SEARCH_DIRS:
        for file_name in file_names:
            candidate = model_dir / file_name
            tried.append(str(candidate))
            if candidate.exists():
                return candidate

    LOGGER.error("Missing model file. Tried: %s", ", ".join(tried))
    return None


def _load_pickle_candidates(label: str, *file_names: str) -> Any:
    model_path = _resolve_model_path(*file_names)
    if model_path is None:
        return None
    return _load_pickle(model_path, label)


def load_models() -> None:
    MODELS["disease_model"] = _load_pickle_candidates("disease_symptom_model", "disease_symptom_model.pkl")
    MODELS["disease_label_encoder"] = _load_pickle_candidates("disease_label_encoder", "disease_label_encoder.pkl")
    feature_names = _load_pickle_candidates("disease_feature_names", "disease_feature_names.pkl")
    MODELS["disease_feature_names"] = list(feature_names) if feature_names is not None else []

    MODELS["breast_cancer_mlp"] = _load_pickle_candidates("breast_cancer_mlp", "breast_cancer_mlp.pkl")
    MODELS["breast_cancer_scaler"] = _load_pickle_candidates("breast_cancer_scaler", "breast_cancer_scaler.pkl")
    breast_features = _load_pickle_candidates("breast_cancer_features", "breast_cancer_features.pkl")
    MODELS["breast_cancer_features"] = list(breast_features) if breast_features is not None else []

    MODELS["diabetes_model"] = _load_pickle_candidates(
        "diabetes_model",
        "diabetes_model (1).pkl",
        "diabetes_model.pkl",
        "diabetes_model__1_.pkl",
    )
    MODELS["diabetes_scaler"] = _load_pickle_candidates(
        "diabetes_scaler",
        "scaler (1).pkl",
        "scaler.pkl",
        "scaler__1_.pkl",
        "diabetes_scaler.pkl",
    )

    MODELS["heart_disease_model"] = _load_pickle_candidates(
        "heart_disease_model",
        "heart_disease_model.pkl",
        "heart_disease_model - Copy.pkl",
    )


def _get_confidence(model: Any, values: np.ndarray) -> float:
    try:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(values)[0]
            return float(np.max(proba))
    except Exception:
        pass
    return 1.0


def _build_chart_base64(model_name: str, inputs: dict[str, Any]) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))

    if model_name == "disease":
        symptoms = list(inputs.get("symptoms", []))[:10]
        labels = [sym.replace("_", " ").title() for sym in symptoms] or ["No Symptoms"]
        values = [1] * len(labels)
        ax.barh(labels, values, color="#00B4A6")
        ax.set_title("Top Matched Symptoms")
        ax.set_xlabel("Matched")
    elif model_name == "breast_cancer":
        numeric = {k: float(v) for k, v in inputs.items() if _is_number(v)}
        items = list(numeric.items())[:8]
        labels = [k.replace("_", " ") for k, _ in items] or ["No Data"]
        values = [v for _, v in items] or [0.0]
        ax.plot(labels, values, marker="o", color="#0A1628")
        ax.fill_between(range(len(values)), values, color="#00B4A6", alpha=0.2)
        ax.set_title("Tumor Feature Profile")
    elif model_name == "diabetes":
        labels = []
        values = []
        for key in DIABETES_FEATURES:
            if key in inputs:
                labels.append(key)
                values.append(_coerce_float(inputs.get(key), 0.0))
        labels = labels or ["No Data"]
        values = values or [0.0]
        ax.bar(labels, values, color="#0A1628")
        ax.set_title("Diabetes Input Values")
        ax.tick_params(axis="x", rotation=30)
    else:
        labels = []
        values = []
        for key in HEART_FEATURES:
            if key in inputs:
                labels.append(key)
                values.append(_coerce_float(inputs.get(key), 0.0))
        labels = labels or ["No Data"]
        values = values or [0.0]
        ax.bar(labels, values, color="#00B4A6")
        ax.set_title("Heart Risk Factors")
        ax.tick_params(axis="x", rotation=30)

    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=140)
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _validate_numeric_payload(payload: dict[str, Any], keys: list[str]) -> np.ndarray:
    values: list[float] = []
    for key in keys:
        if key not in payload:
            raise ValueError(f"Missing field: {key}")
        values.append(float(payload[key]))
    return np.array([values], dtype=float)


def _coerce_float(value: Any, default: float) -> float:
    try:
        text = str(value).strip()
        if not text:
            return float(default)
        parsed = float(text)
        if not np.isfinite(parsed):
            return float(default)
        return parsed
    except Exception:
        return float(default)


def _coerce_choice(value: Any, allowed: list[int], default: int) -> int:
    parsed = int(round(_coerce_float(value, float(default))))
    if parsed in allowed:
        return parsed
    return default if default in allowed else allowed[0]


def _heart_feature_order() -> list[str]:
    return HEART_NUMERIC_FEATURES + [
        f"{column}_{category}"
        for column, categories in HEART_CATEGORICAL_FEATURES.items()
        for category in categories
    ]


def preprocess_heart(data: dict[str, Any]) -> np.ndarray:
    numeric = HEART_NUMERIC_FEATURES
    categoricals = HEART_CATEGORICAL_FEATURES
    numeric_defaults = {"age": 45.0, "trestbps": 130.0, "chol": 200.0, "thalach": 150.0, "oldpeak": 0.0}
    categorical_defaults = {"sex": 1, "cp": 0, "fbs": 0, "restecg": 0, "exang": 0, "slope": 1, "ca": 0, "thal": 2}

    row: dict[str, float] = {col: _coerce_float(data.get(col), numeric_defaults[col]) for col in numeric}
    for col, vals in categoricals.items():
        user_val = _coerce_choice(data.get(col), vals, categorical_defaults[col])
        for value in vals:
            row[f"{col}_{value}"] = 1.0 if user_val == value else 0.0
    col_order = _heart_feature_order()
    return np.array([[row[col] for col in col_order]], dtype=float)


def preprocess_diabetes(data: dict[str, Any]) -> np.ndarray:
    scaler = MODELS["diabetes_scaler"]
    if scaler is None:
        raise RuntimeError("Diabetes scaler unavailable")

    defaults = {
        "Pregnancies": 0.0,
        "Glucose": 100.0,
        "BloodPressure": 80.0,
        "SkinThickness": 20.0,
        "Insulin": 80.0,
        "BMI": 25.0,
        "DiabetesPedigreeFunction": 0.2,
        "Age": 35.0,
    }

    preg = max(0.0, _coerce_float(data.get("Pregnancies"), defaults["Pregnancies"]))
    gluc = max(0.0, _coerce_float(data.get("Glucose"), defaults["Glucose"]))
    bp = max(0.0, _coerce_float(data.get("BloodPressure"), defaults["BloodPressure"]))
    skin = max(0.0, _coerce_float(data.get("SkinThickness"), defaults["SkinThickness"]))
    ins = max(0.0, _coerce_float(data.get("Insulin"), defaults["Insulin"]))
    bmi = max(0.0, _coerce_float(data.get("BMI"), defaults["BMI"]))
    dpf = max(0.0, _coerce_float(data.get("DiabetesPedigreeFunction"), defaults["DiabetesPedigreeFunction"]))
    age = max(1.0, _coerce_float(data.get("Age"), defaults["Age"]))

    bmi_age = bmi * age
    glucose_bmi = gluc * bmi
    age_group = 0 if age <= 30 else (1 if age <= 45 else (2 if age <= 60 else 3))

    features = np.array(
        [[preg, gluc, bp, skin, ins, bmi, dpf, age, bmi_age, glucose_bmi, age_group]],
        dtype=float,
    )
    return scaler.transform(features)


def safe_predict(model: Any, values: np.ndarray, name: str = "model") -> tuple[Any, float]:
    expected = getattr(model, "n_features_in_", None)
    if expected and values.shape[1] != expected:
        raise ValueError(f"{name}: expected {expected} features, got {values.shape[1]}")
    prediction = model.predict(values)[0]
    confidence = _model_probability(model, values)[0]
    return prediction, confidence


def _initialize_guardrails() -> None:
    global METRICS_PROVIDER, MESSAGE_GENERATOR
    METRICS_PROVIDER = ModelMetricsProvider(MODELS)
    MESSAGE_GENERATOR = ResultMessageGenerator(METRICS_PROVIDER)


def _ensure_guardrails() -> tuple[ModelMetricsProvider, ResultMessageGenerator]:
    if METRICS_PROVIDER is None or MESSAGE_GENERATOR is None:
        _initialize_guardrails()
    # Satisfies type-checkers and runtime guards.
    assert METRICS_PROVIDER is not None
    assert MESSAGE_GENERATOR is not None
    return METRICS_PROVIDER, MESSAGE_GENERATOR


def _model_probability(model: Any, values: np.ndarray) -> tuple[float, list[float]]:
    if hasattr(model, "predict_proba"):
        try:
            proba = np.array(model.predict_proba(values)[0], dtype=float)
            return float(np.max(proba)), [float(item) for item in proba.tolist()]
        except Exception:
            pass
    return 0.85, []


def _top_feature_contributions(values: dict[str, float], limit: int = 8) -> dict[str, float]:
    ranked = sorted(values.items(), key=lambda item: abs(item[1]), reverse=True)
    return {key: round(float(value), 4) for key, value in ranked[:limit]}


def _build_transparency_payload(
    model_name: str,
    payload: dict[str, Any],
    prediction: str,
    raw_confidence: float,
    runtime_model: Any,
    feature_vector: np.ndarray,
    feature_names: list[str],
) -> dict[str, Any]:
    metrics_provider, message_generator = _ensure_guardrails()

    validation = INPUT_VALIDATOR.validate_payload(model_name, payload)
    data_quality = DATA_QUALITY_TRACKER.summarize_payload(model_name, payload)

    calibrated = CONFIDENCE_CALIBRATOR.calibrate_prediction(raw_confidence, model_name)
    mc_uncertainty = CONFIDENCE_CALIBRATOR.monte_carlo_uncertainty(
        feature_vector,
        n_iterations=80,
        predict_fn=lambda values: _model_probability(runtime_model, values)[0],
    )

    explainability = EXPLAINABILITY.get_shap_values(runtime_model, feature_vector, feature_names=feature_names)
    explain_values = explainability.get("values", {})
    if not isinstance(explain_values, dict):
        explain_values = {}
    top_contributions = _top_feature_contributions({str(k): float(v) for k, v in explain_values.items()})
    explainability["values"] = top_contributions

    unusual_patterns = EXPLAINABILITY.identify_unusual_patterns(payload, INPUT_VALIDATOR.feature_ranges)
    explanation_text = EXPLAINABILITY.generate_explanation_text(explainability, feature_names=feature_names)

    model_info = metrics_provider.get_model_info(model_name)
    performance_metrics = metrics_provider.get_performance_metrics(model_name)
    demographic_performance = metrics_provider.get_demographic_performance(model_name)

    disclosure = message_generator.generate_disclosure_message(model_name, prediction, calibrated)
    limitations = message_generator.generate_limitation_warning(model_name, payload) + unusual_patterns

    return {
        "confidence": calibrated["confidence"],
        "confidence_raw": raw_confidence,
        "confidence_interval": calibrated["confidence_interval"],
        "confidence_range": calibrated["confidence_range"],
        "uncertainty": mc_uncertainty,
        "validation": validation,
        "data_quality": data_quality,
        "model_info": model_info,
        "performance_metrics": performance_metrics,
        "demographic_performance": demographic_performance,
        "disclosure": disclosure,
        "limitations": limitations,
        "explainability": {
            "method": explainability.get("method", "fallback"),
            "feature_contributions": top_contributions,
            "summary": explanation_text,
            "unusual_patterns": unusual_patterns,
        },
    }


def _disease_recommendations(prediction: str) -> dict[str, Any]:
    disease_map = RECOMMENDATIONS.get("disease", {})
    key = prediction.strip().lower()
    entry = disease_map.get(key) or {
        "precautions": [
            "Track symptom progression daily and note any new changes.",
            "Avoid self-medication without clinician guidance.",
            "Seek in-person consultation if symptoms worsen.",
        ],
        "recommendations": [
            "Follow physician-directed testing and treatment.",
            "Maintain hydration and adequate rest.",
            "Use follow-up visits to confirm diagnosis and recovery.",
        ],
        "urgency": "medium",
    }
    return entry


def _recommendation_bundle(model_name: str, prediction: str) -> dict[str, Any]:
    if model_name == "disease":
        return _disease_recommendations(prediction)

    result_key = "positive"
    healthy_words = ["healthy", "benign", "non-diabetic", "negative"]
    if any(word in prediction.strip().lower() for word in healthy_words):
        result_key = "negative"
    model_bundle = RECOMMENDATIONS.get(model_name, {})
    return model_bundle.get(result_key, {"precautions": [], "recommendations": [], "urgency": "low"})


def _model_title(model_name: str) -> str:
    mapping = {
        "disease": "Disease Symptom Predictor",
        "breast_cancer": "Breast Cancer Predictor",
        "diabetes": "Diabetes Predictor",
        "heart": "Heart Disease Predictor",
    }
    return mapping.get(model_name, model_name.title())


def _report_temp_dir() -> Path:
    linux_tmp = Path("/tmp")
    if linux_tmp.exists():
        return linux_tmp
    return Path(tempfile.gettempdir())


def _decode_chart_image(data_uri: str) -> bytes | None:
    raw = str(data_uri or "").strip()
    if not raw:
        return None
    try:
        if "," in raw:
            raw = raw.split(",", 1)[1]
        return base64.b64decode(raw)
    except Exception:
        return None


_INPUT_LABELS = {
    "Age": "Age (years)",
    "age": "Age (years)",
    "Pregnancies": "Number of pregnancies",
    "BMI": "BMI (kg/m2)",
    "Glucose": "Glucose (mg/dL)",
    "BloodPressure": "Blood pressure, diastolic (mmHg)",
    "SkinThickness": "Skin fold thickness (mm)",
    "Insulin": "Insulin level (mu U/mL)",
    "DiabetesPedigreeFunction": "Diabetes pedigree function",
    "sex": "Sex",
    "cp": "Chest pain type",
    "trestbps": "Resting blood pressure (mmHg)",
    "chol": "Cholesterol (mg/dL)",
    "fbs": "Fasting blood sugar > 120 mg/dL",
    "restecg": "Resting ECG result",
    "thalach": "Maximum heart rate",
    "exang": "Exercise-induced angina",
    "oldpeak": "ST depression (oldpeak)",
    "slope": "ST slope",
    "ca": "Number of major vessels",
    "thal": "Thalassemia",
}


def _format_report_timestamp(raw_value: Any) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return datetime.now().strftime("%d %b %Y, %H:%M")
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%d %b %Y, %H:%M")
    except Exception:
        return raw[:19].replace("T", " ")


def _risk_level(prediction: str, confidence: float) -> str:
    is_positive = prediction in {"Diabetic", "At Risk", "Malignant"}
    if not is_positive:
        return "Low"
    if confidence >= 0.80:
        return "High"
    return "Medium"


def _friendly_input_rows(model_name: str, inputs: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    excluded = {"symptoms", "weight_kg", "height_cm", "dpf_helper"}

    if model_name == "disease":
        symptoms = inputs.get("symptoms", [])
        if isinstance(symptoms, list) and symptoms:
            cleaned = [str(symptom).replace("_", " ").strip().title() for symptom in symptoms]
            preview = ", ".join(cleaned[:12])
            if len(cleaned) > 12:
                preview += f" (+{len(cleaned) - 12} more)"
        else:
            preview = "No symptoms selected"
        return [("Selected symptoms", preview)]

    for key, value in inputs.items():
        if key in excluded:
            continue
        label = _INPUT_LABELS.get(str(key), str(key).replace("_", " ").title())
        text_value = str(value).strip() or "N/A"
        rows.append((label, text_value))

    if not rows:
        rows.append(("Input data", "No values submitted"))
    return rows


def _chart_flowable(image_bytes: bytes, max_width: float, max_height: float) -> RLImage | None:
    if not image_bytes:
        return None
    try:
        image_reader = ImageReader(io.BytesIO(image_bytes))
        img_width, img_height = image_reader.getSize()
        if img_width <= 0 or img_height <= 0:
            return None

        scale = min(max_width / img_width, max_height / img_height)
        scaled_width = max(1.0, img_width * scale)
        scaled_height = max(1.0, img_height * scale)

        image = RLImage(io.BytesIO(image_bytes), width=scaled_width, height=scaled_height)
        image.hAlign = "CENTER"
        return image
    except Exception:
        return None


def _draw_report_footer(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
    canvas.line(doc.leftMargin, 1.5 * cm, A4[0] - doc.rightMargin, 1.5 * cm)

    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(doc.leftMargin, 1.0 * cm, "MediAI Health Screening Report")
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.0 * cm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _generate_pdf_report(payload: dict[str, Any], file_path: Path) -> None:
    model_name = str(payload.get("model", "unknown"))
    prediction = str(payload.get("prediction", "N/A"))
    confidence = float(payload.get("confidence", 0.0) or 0.0)
    confidence_interval = payload.get("confidence_interval", {}) or {}
    confidence_low = _coerce_float(confidence_interval.get("lower"), max(0.03, confidence - 0.05))
    confidence_high = _coerce_float(confidence_interval.get("upper"), min(0.97, confidence + 0.05))
    confidence_range = str(payload.get("confidence_range") or f"{round(confidence_low * 100)}-{round(confidence_high * 100)}%")
    inputs = payload.get("inputs", {}) or {}
    if not isinstance(inputs, dict):
        inputs = {}
    performance_metrics = payload.get("performance_metrics", {}) or {}
    if not isinstance(performance_metrics, dict):
        performance_metrics = {}
    model_info = payload.get("model_info", {}) or {}
    if not isinstance(model_info, dict):
        model_info = {}
    disclosure = payload.get("disclosure", {}) or {}
    if not isinstance(disclosure, dict):
        disclosure = {}
    limitations = payload.get("limitations", [])
    if not isinstance(limitations, list):
        limitations = []
    validation = payload.get("validation", {}) or {}
    if not isinstance(validation, dict):
        validation = {}
    data_quality = payload.get("data_quality", {}) or {}
    if not isinstance(data_quality, dict):
        data_quality = {}

    notes = payload.get("advice")
    if not isinstance(notes, dict):
        notes = _recommendation_bundle(model_name, prediction)

    chart_main = _decode_chart_image(str(payload.get("chart_main", "")))
    chart_pie = _decode_chart_image(str(payload.get("chart_pie", "")))
    if chart_main is None:
        chart_main = _decode_chart_image(str(payload.get("chart_base64", "")))

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.8 * cm,
        bottomMargin=2.0 * cm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B1F3A")
    teal = colors.HexColor("#0F766E")
    success = colors.HexColor("#38A169")
    warning = colors.HexColor("#D69E2E")
    danger = colors.HexColor("#E53E3E")
    risk_level = _risk_level(prediction, confidence)
    risk_color = {"Low": success, "Medium": warning, "High": danger}.get(risk_level, warning)
    confidence_pct = max(0, min(100, round(confidence * 100)))

    title_style = ParagraphStyle(
        "report_title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.white,
    )
    meta_style = ParagraphStyle(
        "report_meta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#D1D5DB"),
    )
    meta_right_style = ParagraphStyle(
        "report_meta_right",
        parent=meta_style,
        alignment=2,
    )
    section_style = ParagraphStyle(
        "report_section",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=teal,
        spaceBefore=10,
        spaceAfter=6,
    )
    card_heading_style = ParagraphStyle(
        "report_card_heading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        alignment=1,
    )
    card_value_style = ParagraphStyle(
        "report_card_value",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=navy,
        alignment=1,
    )
    table_header_style = ParagraphStyle(
        "report_table_header",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
    )
    table_body_style = ParagraphStyle(
        "report_table_body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1F2937"),
    )
    list_item_style = ParagraphStyle(
        "report_list_item",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=3,
    )
    panel_heading_style = ParagraphStyle(
        "report_panel_heading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
        spaceBefore=4,
        spaceAfter=4,
    )
    muted_style = ParagraphStyle(
        "report_muted",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
    )
    disclaimer_style = ParagraphStyle(
        "report_disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    generated_date = _format_report_timestamp(payload.get("timestamp"))
    report_id = file_path.stem.upper()
    story = []

    header_left = [
        Paragraph("MediAI Health Screening Report", title_style),
        Paragraph(f"{escape(_model_title(model_name))} | Generated: {escape(generated_date)}", meta_style),
    ]
    header_right = [
        Paragraph("Report ID", meta_right_style),
        Paragraph(escape(report_id), meta_right_style),
    ]
    header = Table(
        [[header_left, header_right]],
        colWidths=[doc.width * 0.72, doc.width * 0.28],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), navy),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend([header, Spacer(1, 0.4 * cm)])

    risk_value_style = ParagraphStyle(
        "risk_value",
        parent=card_value_style,
        textColor=risk_color,
    )
    result_table = Table(
        [
            [
                Paragraph("Prediction", card_heading_style),
                Paragraph("Risk Level", card_heading_style),
                Paragraph("Calibrated Confidence", card_heading_style),
            ],
            [
                Paragraph(escape(prediction), card_value_style),
                Paragraph(escape(risk_level), risk_value_style),
                Paragraph(escape(confidence_range), card_value_style),
            ],
        ],
        colWidths=[doc.width * 0.42, doc.width * 0.29, doc.width * 0.29],
    )
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([result_table, Spacer(1, 0.35 * cm)])

    dataset_info = model_info.get("training_dataset", {})
    if isinstance(dataset_info, dict):
        dataset_name = str(dataset_info.get("name", "Unknown dataset"))
        dataset_cases = str(dataset_info.get("cases", "N/A"))
        dataset_demo = str(dataset_info.get("demographics", "Demographic details unavailable"))
    else:
        dataset_name = "Unknown dataset"
        dataset_cases = "N/A"
        dataset_demo = "Demographic details unavailable"

    disclosure_lines: list[str] = []
    if disclosure.get("headline"):
        disclosure_lines.append(str(disclosure.get("headline")))
    disclosure_lines.append(f"Model algorithm: {model_info.get('algorithm', 'Unknown')}")
    disclosure_lines.append(f"Training dataset: {dataset_name} ({dataset_cases} cases)")
    disclosure_lines.append(dataset_demo)
    if disclosure.get("error_margin_note"):
        disclosure_lines.append(str(disclosure.get("error_margin_note")))

    disclosure_panel = Table(
        [[Paragraph("Transparency Disclosure", card_heading_style)], [[Paragraph(escape(line), table_body_style) for line in disclosure_lines]]],
        colWidths=[doc.width],
    )
    disclosure_panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([disclosure_panel, Spacer(1, 0.45 * cm)])

    if performance_metrics:
        metric_labels = {
            "accuracy": "Accuracy",
            "sensitivity": "Sensitivity",
            "specificity": "Specificity",
            "precision": "Precision",
            "f1": "F1 Score",
            "auc_roc": "AUC-ROC",
            "auc_pr": "AUC-PR",
            "false_positive_rate": "False Positive Rate",
            "false_negative_rate": "False Negative Rate",
        }
        metric_order = [
            "accuracy",
            "sensitivity",
            "specificity",
            "precision",
            "f1",
            "auc_roc",
            "auc_pr",
            "false_positive_rate",
            "false_negative_rate",
        ]
        metric_rows = [[Paragraph("Metric", table_header_style), Paragraph("Value", table_header_style)]]
        for key in metric_order:
            if key not in performance_metrics:
                continue
            raw_value = performance_metrics.get(key)
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 3:
                mean, low, high = (_coerce_float(raw_value[0], 0.0), _coerce_float(raw_value[1], 0.0), _coerce_float(raw_value[2], 0.0))
                formatted = f"{mean * 100:.1f}% ({low * 100:.1f}-{high * 100:.1f}%)"
            else:
                numeric = _coerce_float(raw_value, 0.0)
                formatted = f"{numeric * 100:.1f}%"
            metric_rows.append(
                [
                    Paragraph(escape(metric_labels.get(key, key.replace("_", " ").title())), table_body_style),
                    Paragraph(escape(formatted), table_body_style),
                ]
            )

        metric_table = Table(metric_rows, colWidths=[doc.width * 0.45, doc.width * 0.55], repeatRows=1)
        metric_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), navy),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([Paragraph("Performance Metrics (Validation Estimates)", section_style), metric_table, Spacer(1, 0.45 * cm)])

    chart_width = (doc.width - 0.4 * cm) / 2
    chart_height = 6.5 * cm
    if chart_main or chart_pie:
        story.append(Paragraph("Visual Analysis", section_style))
        chart_cards: list[Table] = []
        for title, chart_bytes in [("Key Factor Analysis", chart_main), ("Risk Distribution", chart_pie)]:
            if chart_bytes is None:
                chart_content: Any = Paragraph("Chart unavailable", muted_style)
            else:
                chart_content = _chart_flowable(chart_bytes, chart_width - 0.8 * cm, chart_height)
                if chart_content is None:
                    chart_content = Paragraph("Chart unavailable", muted_style)

            card = Table([[Paragraph(title, card_heading_style)], [chart_content]], colWidths=[chart_width])
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            chart_cards.append(card)

        chart_grid = Table([chart_cards], colWidths=[chart_width, chart_width], hAlign="LEFT")
        chart_grid.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.extend([chart_grid, Spacer(1, 0.4 * cm)])

    story.append(Paragraph("Input Summary", section_style))
    rows = [[Paragraph("Parameter", table_header_style), Paragraph("Value", table_header_style)]]
    for label, value in _friendly_input_rows(model_name, inputs):
        rows.append([Paragraph(escape(label), table_body_style), Paragraph(escape(value), table_body_style)])

    summary = Table(rows, colWidths=[doc.width * 0.36, doc.width * 0.64], repeatRows=1)
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary, Spacer(1, 0.5 * cm)])

    quality_lines: list[str] = []
    validation_warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
    validation_outliers = validation.get("outliers", []) if isinstance(validation.get("outliers"), list) else []
    required_state = data_quality.get("required_field_check", {})
    if isinstance(required_state, dict) and required_state.get("missing_critical"):
        quality_lines.append(
            f"Missing critical fields: {', '.join([str(item) for item in required_state.get('missing_critical', [])])}"
        )
    if validation_warnings:
        quality_lines.append(f"Validation warnings: {len(validation_warnings)}")
    if validation_outliers:
        quality_lines.append(f"Outlier flags: {len(validation_outliers)}")
    imputed = data_quality.get("imputed_fields", [])
    if isinstance(imputed, list) and imputed:
        quality_lines.append(f"Imputed fields: {', '.join([str(item) for item in imputed])}")
    if not quality_lines:
        quality_lines.append("Input quality checks found no major issues.")

    quality_panel = Table(
        [[Paragraph("Data Quality Checks", card_heading_style)], [[Paragraph(escape(line), table_body_style) for line in quality_lines]]],
        colWidths=[doc.width],
    )
    quality_panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([quality_panel, Spacer(1, 0.45 * cm)])

    precautions = notes.get("precautions", [])
    recommendations = notes.get("recommendations", [])
    if not isinstance(precautions, list):
        precautions = []
    if not isinstance(recommendations, list):
        recommendations = []

    if precautions or recommendations:
        story.append(Paragraph("Clinical Guidance", section_style))

        left_items = precautions[:8] or ["No specific precautions provided."]
        right_items = recommendations[:8] or ["No specific recommendations provided."]

        left_flow = [Paragraph(f"- {escape(str(item))}", list_item_style) for item in left_items]
        right_flow = [Paragraph(f"- {escape(str(item))}", list_item_style) for item in right_items]

        left_panel = Table([[Paragraph("Precautions", panel_heading_style)], [left_flow]], colWidths=[chart_width])
        right_panel = Table([[Paragraph("Recommendations", panel_heading_style)], [right_flow]], colWidths=[chart_width])

        for panel in [left_panel, right_panel]:
            panel.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )

        guidance = Table([[left_panel, right_panel]], colWidths=[chart_width, chart_width], hAlign="LEFT")
        guidance.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.extend([guidance, Spacer(1, 0.3 * cm)])

    if limitations:
        story.append(Paragraph("Limitations & Cautions", section_style))
        limitation_items = [Paragraph(f"- {escape(str(item))}", list_item_style) for item in limitations[:8]]
        limitation_panel = Table([[limitation_items]], colWidths=[doc.width])
        limitation_panel.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FDBA74")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([limitation_panel, Spacer(1, 0.3 * cm)])

    disclaimer = Table(
        [[
            Paragraph(
            f"This report is generated by an AI screening tool for informational purposes only. "
            f"Calibrated confidence for this result is {confidence_range}, not absolute certainty. "
            f"Approximate error rates include false positive and false negative outcomes depending on model and population. "
                "Please consult a qualified healthcare professional for diagnosis and treatment decisions.",
                disclaimer_style,
            )
        ]],
        colWidths=[doc.width],
    )
    disclaimer.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(disclaimer)

    doc.build(story, onFirstPage=_draw_report_footer, onLaterPages=_draw_report_footer)


def _compose_prediction_response(
    model_name: str,
    prediction: str,
    payload: dict[str, Any],
    raw_confidence: float,
    runtime_model: Any,
    feature_vector: np.ndarray,
    feature_names: list[str],
    chart_base64: str,
) -> dict[str, Any]:
    transparency = _build_transparency_payload(
        model_name=model_name,
        payload=payload,
        prediction=prediction,
        raw_confidence=raw_confidence,
        runtime_model=runtime_model,
        feature_vector=feature_vector,
        feature_names=feature_names,
    )
    return {
        "prediction": prediction,
        "confidence": transparency["confidence"],
        "model": model_name,
        "chart_base64": chart_base64,
        "advice": _recommendation_bundle(model_name, prediction),
        **transparency,
    }


@app.route("/")
def index():
    cards = [
        {"key": "disease", "title": "Disease Symptom Predictor", "description": "Estimate likely disease from symptoms."},
        {"key": "breast_cancer", "title": "Breast Cancer Predictor", "description": "Analyze tumor features for risk."},
        {"key": "diabetes", "title": "Diabetes Predictor", "description": "Assess diabetes likelihood from vitals."},
        {"key": "heart", "title": "Heart Disease Predictor", "description": "Evaluate cardiovascular risk indicators."},
    ]
    return render_template("index.html", cards=cards)


@app.route("/predict/<model_name>")
def predict_page(model_name: str):
    if model_name not in ALLOWED_MODELS:
        return "Unknown model", 404

    context = {
        "model": model_name,
        "model_title": _model_title(model_name),
        "model_description": MODEL_DESCRIPTIONS.get(model_name, ""),
        "symptoms": MODELS["disease_feature_names"],
        "breast_features": MODELS["breast_cancer_features"],
        "breast_tooltips": BREAST_TOOLTIPS,
        "diabetes_fields": [
            {"name": "Pregnancies", "hint": "Number of pregnancies"},
            {"name": "Glucose", "hint": "Normal fasting glucose: 70 to 99 mg/dL"},
            {"name": "BloodPressure", "hint": "Diastolic BP in mm Hg"},
            {"name": "SkinThickness", "hint": "Triceps skin fold thickness in mm"},
            {"name": "Insulin", "hint": "2-hour serum insulin"},
            {"name": "BMI", "hint": "Body Mass Index"},
            {"name": "DiabetesPedigreeFunction", "hint": "Diabetes pedigree score"},
            {"name": "Age", "hint": "Age in years"},
        ],
        "heart_fields": HEART_FEATURES,
    }
    return render_template("predict.html", **context)


@app.get("/api/model-info/<model_name>")
def api_model_info(model_name: str):
    if model_name not in ALLOWED_MODELS:
        return jsonify({"error": "Unknown model"}), 404
    metrics_provider, _ = _ensure_guardrails()
    return jsonify({"ok": True, "model": model_name, "data": metrics_provider.get_model_info(model_name)})


@app.get("/api/model-metrics/<model_name>")
def api_model_metrics(model_name: str):
    if model_name not in ALLOWED_MODELS:
        return jsonify({"error": "Unknown model"}), 404
    metrics_provider, _ = _ensure_guardrails()
    return jsonify(
        {
            "ok": True,
            "model": model_name,
            "metrics": metrics_provider.get_performance_metrics(model_name),
            "demographic_performance": metrics_provider.get_demographic_performance(model_name),
        }
    )


@app.get("/api/model-cards")
def api_model_cards():
    metrics_provider, _ = _ensure_guardrails()
    return jsonify({"ok": True, "cards": metrics_provider.list_model_cards()})


@app.get("/api/docs")
def api_docs():
    """Lightweight endpoint documentation for the Flask AI services."""

    return jsonify(
        {
            "name": "AI Healthcare Intelligence Platform",
            "version": 1,
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/predict/disease",
                    "description": "Predict likely disease based on selected symptoms.",
                    "request": {"symptoms": ["itching", "fatigue"]},
                },
                {
                    "method": "POST",
                    "path": "/predict/breast_cancer",
                    "description": "Predict breast cancer risk from tumor features.",
                },
                {
                    "method": "POST",
                    "path": "/predict/diabetes",
                    "description": "Predict diabetes risk from vitals/lifestyle inputs.",
                },
                {
                    "method": "POST",
                    "path": "/predict/heart",
                    "description": "Predict heart disease risk from cardiology indicators.",
                },
                {
                    "method": "POST",
                    "path": "/predict/heart-risk",
                    "description": "Alias for /predict/heart (API naming consistency).",
                },
                {
                    "method": "POST",
                    "path": "/predict/cluster",
                    "description": "Unsupervised patient/vitals clustering with anomaly detection (KMeans + DBSCAN + PCA).",
                    "request": {
                        "patients": [{"systolic": 120, "diastolic": 80, "glucose": 95}],
                        "features": ["systolic", "diastolic", "glucose"],
                        "n_clusters": 3,
                        "pca_components": 2,
                        "dbscan_eps": 0.85,
                        "dbscan_min_samples": 5,
                    },
                },
                {
                    "method": "POST",
                    "path": "/predict/treatment",
                    "description": "Simulation-based treatment strategy optimization (tabular Q-learning).",
                    "request": {"systolic": 142, "diastolic": 92, "glucose": 180, "age": 55},
                },
                {
                    "method": "POST",
                    "path": "/predict/image",
                    "description": "Placeholder for medical imaging models (not shipped in this repo).",
                },
            ],
        }
    )


@app.post("/predict/disease")
def predict_disease():
    try:
        if MODELS["disease_model"] is None:
            raise RuntimeError("Disease model unavailable")

        payload = request.get_json(force=True) or {}
        symptoms = payload.get("symptoms", [])
        features = MODELS["disease_feature_names"]
        if not isinstance(symptoms, list):
            raise ValueError("symptoms must be a list")

        vector = np.zeros(len(features), dtype=int)
        active = {str(item).strip().lower() for item in symptoms}
        for index, feature in enumerate(features):
            if str(feature).strip().lower() in active:
                vector[index] = 1

        values = np.array([vector], dtype=float)
        prediction_raw, confidence = safe_predict(MODELS["disease_model"], values, "disease_model")
        if MODELS["disease_label_encoder"] is not None:
            prediction = str(MODELS["disease_label_encoder"].inverse_transform([prediction_raw])[0])
        else:
            prediction = str(prediction_raw)

        chart_base64 = _build_chart_base64("disease", {"symptoms": symptoms})
        payload_with_symptoms = dict(payload)
        payload_with_symptoms["symptoms"] = symptoms
        response = _compose_prediction_response(
            model_name="disease",
            prediction=prediction,
            payload=payload_with_symptoms,
            raw_confidence=confidence,
            runtime_model=MODELS["disease_model"],
            feature_vector=values,
            feature_names=[str(item) for item in features],
            chart_base64=chart_base64,
        )
        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": "Prediction failed", "details": str(exc)}), 500


@app.post("/predict/breast_cancer")
def predict_breast_cancer():
    try:
        model = MODELS["breast_cancer_mlp"]
        scaler = MODELS["breast_cancer_scaler"]
        features = MODELS["breast_cancer_features"]
        if model is None or scaler is None or not features:
            raise RuntimeError("Breast cancer model components unavailable")

        payload = request.get_json(force=True) or {}
        values = _validate_numeric_payload(payload, list(features))
        scaled = scaler.transform(values)
        pred_raw, confidence = safe_predict(model, scaled, "breast_cancer_model")
        pred = int(pred_raw)
        prediction = "Malignant" if pred == 1 else "Benign"

        chart_base64 = _build_chart_base64("breast_cancer", payload)
        response = _compose_prediction_response(
            model_name="breast_cancer",
            prediction=prediction,
            payload=payload,
            raw_confidence=confidence,
            runtime_model=model,
            feature_vector=scaled,
            feature_names=[str(item) for item in features],
            chart_base64=chart_base64,
        )
        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": "Prediction failed", "details": str(exc)}), 500


@app.post("/predict/diabetes")
def predict_diabetes():
    try:
        model = MODELS["diabetes_model"]
        scaler = MODELS["diabetes_scaler"]
        if model is None or scaler is None:
            raise RuntimeError("Diabetes model components unavailable")

        payload = request.get_json(force=True) or {}
        scaled = preprocess_diabetes(payload)
        pred_raw, confidence = safe_predict(model, scaled, "diabetes_model")
        pred = int(pred_raw)
        prediction = "Diabetic" if pred == 1 else "Non-Diabetic"

        chart_base64 = _build_chart_base64("diabetes", payload)
        response = _compose_prediction_response(
            model_name="diabetes",
            prediction=prediction,
            payload=payload,
            raw_confidence=confidence,
            runtime_model=model,
            feature_vector=scaled,
            feature_names=DIABETES_ENGINEERED_FEATURES,
            chart_base64=chart_base64,
        )
        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": "Prediction failed", "details": str(exc)}), 500


@app.post("/predict/heart")
def predict_heart():
    try:
        model = MODELS["heart_disease_model"]
        if model is None:
            raise RuntimeError("Heart disease model unavailable")

        payload = request.get_json(force=True) or {}
        values = preprocess_heart(payload)
        pred_raw, confidence = safe_predict(model, values, "heart_disease_model")
        pred = int(pred_raw)
        prediction = "At Risk" if pred == 1 else "Healthy"

        chart_base64 = _build_chart_base64("heart", payload)
        response = _compose_prediction_response(
            model_name="heart",
            prediction=prediction,
            payload=payload,
            raw_confidence=confidence,
            runtime_model=model,
            feature_vector=values,
            feature_names=_heart_feature_order(),
            chart_base64=chart_base64,
        )
        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": "Prediction failed", "details": str(exc)}), 500


@app.post("/predict/heart-risk")
def predict_heart_risk():
    """Alias for `/predict/heart` to support consistent API naming."""

    return predict_heart()


@app.post("/predict/cluster")
def predict_cluster():
    """Cluster patient records (or vitals snapshots) and detect anomalies."""

    try:
        payload = request.get_json(force=True) or {}
        patients = payload.get("patients", None)
        if not isinstance(patients, list):
            raise ValueError("patients must be a list of records")

        features = payload.get("features")
        if features is not None:
            if not isinstance(features, list) or not all(isinstance(item, str) for item in features):
                raise ValueError("features must be a list of strings")

        result = cluster_patients(
            patients,
            features=features,
            n_clusters=int(payload.get("n_clusters", 3)),
            pca_components=int(payload.get("pca_components", 2)),
            dbscan_eps=float(payload.get("dbscan_eps", 0.85)),
            dbscan_min_samples=int(payload.get("dbscan_min_samples", 5)),
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": "Clustering failed", "details": str(exc)}), 500


@app.post("/predict/treatment")
def predict_treatment():
    """Simulation-based treatment strategy optimization using a Q-learning agent."""

    try:
        payload = request.get_json(force=True) or {}
        agent = get_default_agent()
        recommendation = agent.recommend(payload)
        return jsonify(recommendation.to_dict())
    except Exception as exc:
        return jsonify({"error": "Treatment optimization failed", "details": str(exc)}), 500


@app.post("/predict/image")
def predict_image():
    """Placeholder endpoint for image-based models (e.g., X-ray/CT)."""

    return (
        jsonify(
            {
                "error": "Image prediction not configured",
                "details": "No imaging model is shipped with this repository. Add a CV model and wire it here.",
            }
        ),
        501,
    )


@app.post("/report/generate")
def report_generate():
    try:
        payload = request.get_json(force=True) or {}
        file_name = f"mediAI_{uuid.uuid4().hex[:8]}.pdf"
        temp_dir = _report_temp_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / file_name
        _generate_pdf_report(payload, file_path)
        return jsonify({"report_url": f"/report/download/{file_name}"})
    except Exception as exc:
        return jsonify({"error": "Report generation failed", "details": str(exc)}), 500


@app.get("/report/download/<filename>")
def report_download(filename: str):
    safe_name = Path(filename).name
    file_path = _report_temp_dir() / safe_name
    if not file_path.exists():
        return jsonify({"error": "Report not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=safe_name)


@app.get("/disclaimer")
def disclaimer_page():
    metrics_provider, _ = _ensure_guardrails()
    return render_template("disclaimer.html", model_cards=metrics_provider.list_model_cards())


@app.get("/result")
def result_page():
    return render_template("result.html")


load_models()
_initialize_guardrails()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
