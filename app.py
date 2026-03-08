from __future__ import annotations

import base64
import io
import logging
import os
import pickle
import tempfile
import uuid
from datetime import datetime
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
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
                values.append(float(inputs[key]))
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
                values.append(float(inputs[key]))
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


def preprocess_heart(data: dict[str, Any]) -> np.ndarray:
    numeric = ["age", "trestbps", "chol", "thalach", "oldpeak"]
    categoricals = {
        "sex": [0, 1],
        "cp": [0, 1, 2, 3],
        "fbs": [0, 1],
        "restecg": [0, 1, 2],
        "exang": [0, 1],
        "slope": [0, 1, 2],
        "ca": [0, 1, 2, 3, 4],
        "thal": [1, 2, 3],
    }
    row: dict[str, float] = {col: float(data[col]) for col in numeric}
    for col, vals in categoricals.items():
        user_val = int(float(data[col]))
        for value in vals:
            row[f"{col}_{value}"] = 1.0 if user_val == value else 0.0
    col_order = numeric + [f"{col}_{value}" for col, vals in categoricals.items() for value in vals]
    return np.array([[row[col] for col in col_order]], dtype=float)


def preprocess_diabetes(data: dict[str, Any]) -> np.ndarray:
    scaler = MODELS["diabetes_scaler"]
    if scaler is None:
        raise RuntimeError("Diabetes scaler unavailable")

    preg = float(data["Pregnancies"])
    gluc = float(data["Glucose"])
    bp = float(data["BloodPressure"])
    skin = float(data["SkinThickness"])
    ins = float(data["Insulin"])
    bmi = float(data["BMI"])
    dpf = float(data["DiabetesPedigreeFunction"])
    age = float(data["Age"])

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
    confidence = float(model.predict_proba(values).max()) if hasattr(model, "predict_proba") else 0.85
    return prediction, confidence


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


def _generate_pdf_report(payload: dict[str, Any], file_path: Path) -> None:
    model_name = str(payload.get("model", "unknown"))
    prediction = str(payload.get("prediction", "N/A"))
    confidence = float(payload.get("confidence", 0.0))
    inputs = payload.get("inputs", {}) or {}
    notes = payload.get("advice") or _recommendation_bundle(model_name, prediction)

    chart_main = _decode_chart_image(str(payload.get("chart_main", "")))
    chart_pie = _decode_chart_image(str(payload.get("chart_pie", "")))
    if chart_main is None:
        chart_main = _decode_chart_image(str(payload.get("chart_base64", "")))

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0A1628")
    teal = colors.HexColor("#00B4A6")
    success = colors.HexColor("#38A169")
    danger = colors.HexColor("#E53E3E")
    is_positive = prediction in {"Diabetic", "At Risk", "Malignant"}
    result_color = danger if is_positive else success

    heading = lambda text: Paragraph(
        text,
        ParagraphStyle("H", fontSize=20, textColor=colors.white, fontName="Helvetica-Bold"),
    )
    section = lambda text: Paragraph(
        text,
        ParagraphStyle("S", fontSize=12, textColor=teal, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6),
    )
    body = lambda text: Paragraph(text, ParagraphStyle("B", fontSize=10, leading=16, spaceAfter=5))
    disclaimer = lambda text: Paragraph(
        text,
        ParagraphStyle("DI", fontSize=8, textColor=colors.grey, leading=12, fontName="Helvetica-Oblique"),
    )

    generated_date = str(payload.get("timestamp", "")).strip()[:10] or datetime.now().strftime("%Y-%m-%d")
    story = []

    header = Table(
        [[heading("MediAI Health Report"), Paragraph(generated_date, ParagraphStyle("D", fontSize=9, textColor=colors.grey))]],
        colWidths=[12 * cm, 5 * cm],
    )
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), navy), ("PADDING", (0, 0), (-1, -1), 16)]))
    story.extend([header, Spacer(1, 0.4 * cm)])

    result_table = Table(
        [
            [
                Paragraph(
                    f"<b>{prediction}</b>",
                    ParagraphStyle("R", fontSize=18, textColor=colors.white, fontName="Helvetica-Bold"),
                ),
                Paragraph(
                    f"Confidence: {round(confidence * 100)}%",
                    ParagraphStyle("C", fontSize=12, textColor=colors.white),
                ),
            ]
        ],
        colWidths=[10 * cm, 7 * cm],
    )
    result_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), result_color), ("PADDING", (0, 0), (-1, -1), 14)]))
    story.extend([result_table, Spacer(1, 0.5 * cm)])

    if chart_main:
        story.extend([section("Factor Analysis"), RLImage(io.BytesIO(chart_main), width=14 * cm, height=7 * cm), Spacer(1, 0.3 * cm)])
    if chart_pie:
        story.extend([section("Risk Distribution"), RLImage(io.BytesIO(chart_pie), width=14 * cm, height=7 * cm), Spacer(1, 0.3 * cm)])

    story.append(section("Your Input Summary"))
    rows = [["Parameter", "Value"]]
    excluded = {"symptoms", "weight_kg", "height_cm", "dpf_helper"}
    if model_name == "disease":
        symptoms = inputs.get("symptoms", [])
        if isinstance(symptoms, list):
            joined = ", ".join([str(symptom) for symptom in symptoms[:10]])
            if len(symptoms) > 10:
                joined += "..."
            rows.append(["Symptoms", joined])
    else:
        for key, value in inputs.items():
            if key not in excluded:
                rows.append([str(key), str(value)])

    summary = Table(rows, colWidths=[8 * cm, 9 * cm])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([summary, Spacer(1, 0.5 * cm)])

    if notes.get("precautions") or notes.get("recommendations"):
        story.append(section("Precautions & Recommendations"))
        for item in notes.get("precautions", []):
            story.append(body(f"• {item}"))
        for item in notes.get("recommendations", []):
            story.append(body(f"• {item}"))
        story.append(Spacer(1, 0.3 * cm))

    story.append(
        disclaimer(
            "This report is generated by an AI screening tool for informational purposes only. "
            "It does not constitute medical advice, diagnosis, or treatment. "
            "Please consult a qualified healthcare professional for health concerns."
        )
    )
    doc.build(story)


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
        response = {
            "prediction": prediction,
            "confidence": confidence,
            "model": "disease",
            "chart_base64": chart_base64,
            "advice": _recommendation_bundle("disease", prediction),
        }
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
        response = {
            "prediction": prediction,
            "confidence": confidence,
            "model": "breast_cancer",
            "chart_base64": chart_base64,
            "advice": _recommendation_bundle("breast_cancer", prediction),
        }
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
        response = {
            "prediction": prediction,
            "confidence": confidence,
            "model": "diabetes",
            "chart_base64": chart_base64,
            "advice": _recommendation_bundle("diabetes", prediction),
        }
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
        response = {
            "prediction": prediction,
            "confidence": confidence,
            "model": "heart",
            "chart_base64": chart_base64,
            "advice": _recommendation_bundle("heart", prediction),
        }
        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": "Prediction failed", "details": str(exc)}), 500


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


@app.get("/result")
def result_page():
    return render_template("result.html")


load_models()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
