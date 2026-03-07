"""Model integration layer for loading and scoring multiple healthcare models."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINED_MODELS_DIR = Path(__file__).resolve().parent / "trained_models"
DEFAULT_DATASET = PROJECT_ROOT / "data" / "health_data.csv"

DEFAULT_FEATURES = ["age", "blood_pressure", "cholesterol"]
DEFAULT_TARGET = "diabetes_risk"
DEFAULT_WEIGHTS = {
    "diabetes": 0.30,
    "heart": 0.25,
    "hypertension": 0.20,
    "obesity": 0.15,
    "general": 0.10,
}


class ModelManager:
    """Load models from disk and provide unified prediction APIs."""

    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or TRAINED_MODELS_DIR
        self.models: dict[str, Any] = {}
        self.model_meta: dict[str, dict[str, Any]] = {}
        self.load_status: dict[str, str] = {}

    def bootstrap(self) -> None:
        """Prepare model directory and load every model."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_fallback_model()
        self.load_all_models()

    def _ensure_fallback_model(self) -> None:
        """Create a baseline diabetes model if no model file is available."""
        existing = list(self.models_dir.glob("*.pkl"))
        if existing:
            return
        if not DEFAULT_DATASET.exists():
            LOGGER.warning("No fallback model generated: dataset missing at %s", DEFAULT_DATASET)
            return

        data = pd.read_csv(DEFAULT_DATASET)
        required = DEFAULT_FEATURES + [DEFAULT_TARGET]
        if any(column not in data.columns for column in required):
            LOGGER.warning("No fallback model generated: dataset missing required columns.")
            return

        model = RandomForestClassifier(n_estimators=250, random_state=42, max_depth=6)
        model.fit(data[DEFAULT_FEATURES], data[DEFAULT_TARGET])
        fallback_path = self.models_dir / "diabetes_model.pkl"
        joblib.dump(model, fallback_path)
        LOGGER.info("Created fallback model: %s", fallback_path)

    def load_all_models(self) -> dict[str, str]:
        """Load every pkl model in trained_models directory."""
        self.models.clear()
        self.model_meta.clear()
        self.load_status.clear()

        model_files = sorted(self.models_dir.glob("*.pkl"))
        if not model_files:
            self.load_status["system"] = "No .pkl files found in models/trained_models/"
            return self.load_status

        for model_file in model_files:
            model_name = model_file.stem
            try:
                model = joblib.load(model_file)
                feature_names = list(getattr(model, "feature_names_in_", DEFAULT_FEATURES))
                category = self._model_category(model_name)

                self.models[model_name] = model
                self.model_meta[model_name] = {
                    "file": str(model_file),
                    "feature_names": feature_names,
                    "category": category,
                    "weight": DEFAULT_WEIGHTS.get(category, 1.0),
                }
                self.load_status[model_name] = f"Loaded ({len(feature_names)} features)"
            except Exception as exc:  # pragma: no cover - defensive catch for third-party model files
                self.load_status[model_name] = f"Failed to load: {exc}"
                LOGGER.exception("Failed to load model %s", model_file)

        return self.load_status

    def _model_category(self, model_name: str) -> str:
        """Infer model category from filename prefix."""
        lowered = model_name.lower()
        for key in DEFAULT_WEIGHTS:
            if key in lowered:
                return key
        return "general"

    def _extract_probability(self, model: Any, frame: pd.DataFrame) -> float:
        """Return positive-class probability from a model in [0, 1]."""
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(frame)
            if len(probabilities[0]) >= 2:
                return float(probabilities[0][1])
            return float(max(probabilities[0]))

        if hasattr(model, "decision_function"):
            score = float(model.decision_function(frame)[0])
            return 1.0 / (1.0 + math.exp(-score))

        prediction = float(model.predict(frame)[0])
        return max(0.0, min(1.0, prediction))

    def _risk_level(self, value: float) -> tuple[str, str]:
        """Map probability percentage to label and UI color."""
        if value >= 70:
            return "High", "danger"
        if value >= 40:
            return "Medium", "warning"
        return "Low", "success"

    def predict_all(self, patient_data: dict[str, Any]) -> dict[str, Any]:
        """Run all loaded models and return per-model plus global score."""
        if not self.models:
            raise RuntimeError("No models are loaded. Place .pkl files under models/trained_models/.")

        model_results: dict[str, dict[str, Any]] = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for name, model in self.models.items():
            meta = self.model_meta[name]
            feature_names = meta["feature_names"]
            frame = pd.DataFrame([[patient_data.get(feature, 0) for feature in feature_names]], columns=feature_names)

            probability = self._extract_probability(model, frame)
            probability_pct = round(probability * 100, 2)
            level, ui_class = self._risk_level(probability_pct)
            model_results[name] = {
                "probability": probability,
                "risk_percent": probability_pct,
                "risk_level": level,
                "risk_class": ui_class,
                "features_used": feature_names,
            }

            weight = float(meta["weight"])
            weighted_sum += probability * weight
            total_weight += weight

        global_probability = weighted_sum / total_weight if total_weight else 0.0
        global_percent = round(global_probability * 100, 2)
        global_level, global_class = self._risk_level(global_percent)

        return {
            "patient_data": patient_data,
            "model_results": model_results,
            "global_score": {
                "probability": global_probability,
                "risk_percent": global_percent,
                "risk_level": global_level,
                "risk_class": global_class,
            },
            "model_count": len(model_results),
            "loading_status": self.load_status,
        }
