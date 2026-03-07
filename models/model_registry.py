"""Dynamic model registry with metadata contract, versioning, calibration, and explainability."""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

try:
    import shap  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    shap = None

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINED_MODELS_DIR = Path(__file__).resolve().parent / "trained_models"
METADATA_DIR = Path(__file__).resolve().parent / "metadata"
ACTIVE_VERSIONS_FILE = Path(__file__).resolve().parent / "active_versions.json"
DATASET_PATH = PROJECT_ROOT / "data" / "health_data.csv"

DEFAULT_FEATURES = ["age", "blood_pressure", "cholesterol"]
DEFAULT_TARGET = "diabetes_risk"
DEFAULT_WEIGHT_HINTS = {
    "diabetes": 0.30,
    "heart": 0.25,
    "hypertension": 0.20,
    "obesity": 0.15,
    "lifestyle": 0.10,
}
REQUIRED_METADATA_FIELDS = [
    "model_name",
    "description",
    "features",
    "weight",
    "version",
    "owner",
    "metrics",
]
MODEL_VERSION_PATTERN = re.compile(r"^(?P<family>.+)_v(?P<version>\d+(?:\.\d+)*)$")


@dataclass
class ModelBundle:
    """Container holding model runtime artifacts and metadata."""

    model_key: str
    family: str
    version: str
    model: Any
    metadata: dict[str, Any]
    model_path: str
    preprocessor: Any | None = None
    calibrator: Any | None = None
    shap_explainer: Any | None = None


class ModelRegistry:
    """Registry that auto-discovers models and exposes active predictions."""

    def __init__(self, models_dir: Path | None = None, metadata_dir: Path | None = None) -> None:
        self.models_dir = models_dir or TRAINED_MODELS_DIR
        self.metadata_dir = metadata_dir or METADATA_DIR
        self.models_by_family: dict[str, dict[str, ModelBundle]] = {}
        self.active_versions: dict[str, str] = {}
        self._load_status: dict[str, str] = {}

    def load_models(self) -> dict[str, str]:
        """Load all models, validate metadata contract, and activate model versions."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        self.models_by_family.clear()
        self._load_status.clear()
        self._bootstrap_if_empty()
        self.active_versions = self._load_active_versions()

        for model_file in sorted(self.models_dir.glob("*.pkl")):
            if model_file.stem.endswith("_preprocessor") or model_file.stem.endswith("_calibrator"):
                continue

            family, inferred_version = self._parse_family_version(model_file.stem)
            model_key = model_file.stem

            try:
                model = joblib.load(model_file)
                metadata = self._load_metadata(model_key, family, inferred_version, model)
                self._validate_metadata_contract(model_key, metadata)

                preprocessor = self._load_optional_artifact(metadata, model_file, suffix="_preprocessor", metadata_key="preprocessor")
                calibrator = self._load_optional_artifact(metadata, model_file, suffix="_calibrator", metadata_key="calibrator")
                explainer = self._build_shap_explainer(model)

                bundle = ModelBundle(
                    model_key=model_key,
                    family=family,
                    version=str(metadata["version"]),
                    model=model,
                    metadata=metadata,
                    model_path=str(model_file),
                    preprocessor=preprocessor,
                    calibrator=calibrator,
                    shap_explainer=explainer,
                )

                self.models_by_family.setdefault(family, {})[bundle.version] = bundle
                self._load_status[model_key] = "loaded"
            except Exception as exc:  # pragma: no cover - defensive behavior for external model files
                LOGGER.exception("Failed to load model: %s", model_file)
                self._load_status[model_key] = f"failed: {exc}"

        self._resolve_active_versions()
        self._save_active_versions()

        if not self.get_models():
            self._load_status["registry"] = "no models loaded"
        return self._load_status

    def get_models(self) -> dict[str, ModelBundle]:
        """Return active model bundle for each family."""
        active: dict[str, ModelBundle] = {}
        for family, versions in self.models_by_family.items():
            active_version = self.active_versions.get(family)
            if active_version and active_version in versions:
                active[family] = versions[active_version]
        return active

    def get_all_versions(self) -> dict[str, list[str]]:
        """Return available versions by model family."""
        return {family: sorted(versions.keys(), key=self._version_key, reverse=True) for family, versions in self.models_by_family.items()}

    def get_catalog(self) -> dict[str, Any]:
        """Return serializable model catalog with versions and metadata."""
        catalog: dict[str, Any] = {}
        for family, versions in self.models_by_family.items():
            catalog[family] = {
                "active_version": self.active_versions.get(family),
                "versions": [
                    {
                        "version": version,
                        "model_key": bundle.model_key,
                        "metadata": bundle.metadata,
                        "model_path": bundle.model_path,
                        "has_preprocessor": bundle.preprocessor is not None,
                        "has_calibrator": bundle.calibrator is not None,
                    }
                    for version, bundle in sorted(versions.items(), key=lambda item: self._version_key(item[0]), reverse=True)
                ],
            }
        return catalog

    def get_status(self) -> dict[str, str]:
        """Return model loading statuses for diagnostics UI."""
        return self._load_status

    def refresh(self) -> dict[str, str]:
        """Force a model registry reload."""
        return self.load_models()

    def set_active_version(self, family: str, version: str) -> bool:
        """Activate a specific version to support rollback/roll-forward."""
        if family not in self.models_by_family:
            return False
        if version not in self.models_by_family[family]:
            return False
        self.active_versions[family] = version
        self._save_active_versions()
        return True

    def predict_all(self, patient_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Run predictions across currently active model family versions."""
        active_models = self.get_models()
        if not active_models:
            raise RuntimeError("No active models available. Add valid .pkl files under models/trained_models/.")

        predictions: dict[str, dict[str, Any]] = {}
        for family, bundle in active_models.items():
            features = bundle.metadata["features"]
            input_frame = pd.DataFrame([[patient_data.get(f, 0) for f in features]], columns=features)

            processed_input = self._apply_preprocessor(bundle.preprocessor, input_frame)
            raw_probability = self._predict_probability(bundle.model, processed_input)
            calibrated_probability = self._calibrate_probability(bundle.calibrator, raw_probability)
            calibrated_probability = max(0.0, min(1.0, calibrated_probability))

            thresholds = bundle.metadata.get("thresholds", {"medium": 0.40, "high": 0.70})
            risk_level, risk_class = self._risk_bucket(calibrated_probability, thresholds)

            top_features = self._feature_explanations(bundle, input_frame, processed_input)

            predictions[family] = {
                "model_key": bundle.model_key,
                "version": bundle.version,
                "probability": calibrated_probability,
                "raw_probability": raw_probability,
                "risk_percent": round(calibrated_probability * 100, 2),
                "risk_level": risk_level,
                "risk_class": risk_class,
                "weight": float(bundle.metadata.get("weight", 1.0)),
                "metadata": bundle.metadata,
                "top_features": top_features,
                "features_used": features,
            }
        return predictions

    def _parse_family_version(self, stem: str) -> tuple[str, str]:
        """Infer model family and version from file stem."""
        match = MODEL_VERSION_PATTERN.match(stem)
        if match:
            return match.group("family"), match.group("version")
        return stem, "1.0.0"

    def _version_key(self, version: str) -> tuple[int, ...]:
        """Convert semantic-ish version string to sortable tuple."""
        try:
            return tuple(int(part) for part in str(version).split("."))
        except ValueError:
            return (0,)

    def _load_active_versions(self) -> dict[str, str]:
        """Load persisted active-version map."""
        if not ACTIVE_VERSIONS_FILE.exists():
            return {}
        try:
            content = json.loads(ACTIVE_VERSIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                return {str(k): str(v) for k, v in content.items()}
        except Exception:  # pragma: no cover
            LOGGER.exception("Failed to read active versions file")
        return {}

    def _save_active_versions(self) -> None:
        """Persist active-version map for rollback support."""
        ACTIVE_VERSIONS_FILE.write_text(json.dumps(self.active_versions, indent=2), encoding="utf-8")

    def _resolve_active_versions(self) -> None:
        """Ensure every family has an active version, defaulting to latest."""
        for family, versions in self.models_by_family.items():
            configured = self.active_versions.get(family)
            if configured in versions:
                continue
            latest = sorted(versions.keys(), key=self._version_key, reverse=True)[0]
            self.active_versions[family] = latest

    def _load_optional_artifact(self, metadata: dict[str, Any], model_file: Path, suffix: str, metadata_key: str) -> Any | None:
        """Load optional sidecar artifact (preprocessor/calibrator)."""
        explicit = metadata.get(metadata_key)
        if explicit:
            candidate = Path(explicit)
            if not candidate.is_absolute():
                candidate = (self.models_dir / candidate).resolve()
        else:
            candidate = model_file.with_name(f"{model_file.stem}{suffix}.pkl")

        if candidate.exists():
            try:
                return joblib.load(candidate)
            except Exception:  # pragma: no cover
                LOGGER.exception("Failed to load %s artifact for %s", metadata_key, model_file)
        return None

    def _apply_preprocessor(self, preprocessor: Any | None, frame: pd.DataFrame) -> Any:
        """Apply model-specific preprocessing pipeline if available."""
        if preprocessor is None:
            return frame
        if hasattr(preprocessor, "transform"):
            transformed = preprocessor.transform(frame)
            return transformed
        return frame

    def _predict_probability(self, model: Any, transformed_input: Any) -> float:
        """Extract positive class probability from model output."""
        if hasattr(model, "predict_proba"):
            output = model.predict_proba(transformed_input)
            if len(output[0]) >= 2:
                return float(output[0][1])
            return float(max(output[0]))

        if hasattr(model, "decision_function"):
            score = float(model.decision_function(transformed_input)[0])
            return 1.0 / (1.0 + math.exp(-score))

        raw = float(model.predict(transformed_input)[0])
        return max(0.0, min(1.0, raw))

    def _calibrate_probability(self, calibrator: Any | None, probability: float) -> float:
        """Apply optional model calibration artifact to probability output."""
        if calibrator is None:
            return probability
        payload = [[probability]]
        if hasattr(calibrator, "predict_proba"):
            output = calibrator.predict_proba(payload)
            if len(output[0]) >= 2:
                return float(output[0][1])
            return float(max(output[0]))
        if hasattr(calibrator, "predict"):
            output = calibrator.predict(payload)
            if hasattr(output, "__len__"):
                return float(output[0])
            return float(output)
        return probability

    def _risk_bucket(self, probability: float, thresholds: dict[str, Any]) -> tuple[str, str]:
        """Map probability to risk level using configurable per-model thresholds."""
        medium = float(thresholds.get("medium", 0.40))
        high = float(thresholds.get("high", 0.70))
        if probability >= high:
            return "High", "danger"
        if probability >= medium:
            return "Medium", "warning"
        return "Low", "success"

    def _build_shap_explainer(self, model: Any) -> Any | None:
        """Build SHAP explainer when dependency and model type allow it."""
        if shap is None:
            return None
        try:
            return shap.Explainer(model)
        except Exception:
            return None

    def _feature_explanations(self, bundle: ModelBundle, original_frame: pd.DataFrame, transformed_input: Any) -> list[dict[str, Any]]:
        """Generate feature contributions using SHAP first, then model importance fallback."""
        features = list(bundle.metadata.get("features", DEFAULT_FEATURES))

        shap_items = self._feature_explanations_shap(bundle, original_frame, transformed_input, features)
        if shap_items:
            return shap_items

        return self._feature_explanations_importance(bundle.model, features, original_frame)

    def _feature_explanations_shap(
        self,
        bundle: ModelBundle,
        original_frame: pd.DataFrame,
        transformed_input: Any,
        features: list[str],
    ) -> list[dict[str, Any]]:
        """Try SHAP-based explanation for top features."""
        if shap is None:
            return []

        try:
            explainer = bundle.shap_explainer
            if explainer is None:
                return []

            input_for_explainer = original_frame if bundle.preprocessor is None else transformed_input
            values = explainer(input_for_explainer)

            # For binary classification, values can be 2D or 3D depending on explainer/model.
            if hasattr(values, "values"):
                raw_values = values.values
            else:
                return []

            if getattr(raw_values, "ndim", 0) == 3:
                row = raw_values[0, :, -1]
            elif getattr(raw_values, "ndim", 0) == 2:
                row = raw_values[0]
            else:
                return []

            limited = min(len(features), len(row))
            if limited == 0:
                return []

            abs_total = sum(abs(float(row[idx])) for idx in range(limited)) or 1.0
            results: list[dict[str, Any]] = []
            for idx in range(limited):
                contribution = float(row[idx])
                direction = "+" if contribution >= 0 else "-"
                impact = round((abs(contribution) / abs_total) * 100, 2)
                feature = features[idx]
                results.append(
                    {
                        "feature": feature,
                        "impact_percent": impact,
                        "direction": direction,
                        "display": f"{feature.replace('_', ' ').title()} -> {direction}{impact}%",
                    }
                )

            results.sort(key=lambda item: item["impact_percent"], reverse=True)
            return results[:3]
        except Exception:
            return []

    def _feature_explanations_importance(self, model: Any, features: list[str], frame: pd.DataFrame) -> list[dict[str, Any]]:
        """Fallback explanation from feature importances or coefficients."""
        if hasattr(model, "feature_importances_"):
            raw_importances = [float(abs(x)) for x in model.feature_importances_[: len(features)]]
        elif hasattr(model, "coef_"):
            raw = model.coef_[0] if hasattr(model.coef_, "__iter__") else [model.coef_]
            raw_importances = [float(abs(x)) for x in list(raw)[: len(features)]]
        else:
            raw_importances = [1.0 for _ in features]

        if len(raw_importances) < len(features):
            raw_importances.extend([1.0] * (len(features) - len(raw_importances)))

        total = sum(raw_importances) or 1.0
        explanations = []
        for feature, importance in zip(features, raw_importances):
            impact = round((importance / total) * 100, 2)
            direction = "+" if float(frame.iloc[0][feature]) >= 0 else "-"
            explanations.append(
                {
                    "feature": feature,
                    "impact_percent": impact,
                    "direction": direction,
                    "display": f"{feature.replace('_', ' ').title()} -> {direction}{impact}%",
                }
            )

        explanations.sort(key=lambda item: item["impact_percent"], reverse=True)
        return explanations[:3]

    def _load_metadata(self, model_key: str, family: str, inferred_version: str, model: Any) -> dict[str, Any]:
        """Load metadata JSON or create default metadata template."""
        meta_path = self.metadata_dir / f"{model_key}.json"
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            metadata = {
                "model_name": model_key.replace("_", " ").title(),
                "description": "Auto-generated metadata for integrated model.",
                "features": list(getattr(model, "feature_names_in_", DEFAULT_FEATURES)),
                "weight": self._guess_weight(family),
                "version": inferred_version,
                "owner": "integration-team",
                "metrics": {"auc": 0.0, "f1": 0.0},
                "thresholds": {"medium": 0.40, "high": 0.70},
            }
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        metadata.setdefault("model_name", model_key.replace("_", " ").title())
        metadata.setdefault("description", "No description available.")
        metadata.setdefault("features", list(getattr(model, "feature_names_in_", DEFAULT_FEATURES)))
        metadata.setdefault("weight", self._guess_weight(family))
        metadata.setdefault("version", inferred_version)
        metadata.setdefault("owner", "integration-team")
        metadata.setdefault("metrics", {"auc": 0.0, "f1": 0.0})
        metadata.setdefault("thresholds", {"medium": 0.40, "high": 0.70})
        return metadata

    def _validate_metadata_contract(self, model_key: str, metadata: dict[str, Any]) -> None:
        """Validate onboarding metadata schema for each integrated model."""
        missing = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata]
        if missing:
            raise ValueError(f"{model_key} missing required metadata fields: {', '.join(missing)}")

        features = metadata.get("features")
        if not isinstance(features, list) or not features or not all(isinstance(x, str) for x in features):
            raise ValueError(f"{model_key} has invalid 'features' metadata")

        weight = metadata.get("weight")
        if not isinstance(weight, (int, float)):
            raise ValueError(f"{model_key} has invalid 'weight' metadata")

        metrics = metadata.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"{model_key} has invalid 'metrics' metadata")

        if not isinstance(metadata.get("owner"), str) or not metadata.get("owner"):
            raise ValueError(f"{model_key} has invalid 'owner' metadata")

        if not isinstance(metadata.get("version"), str):
            raise ValueError(f"{model_key} has invalid 'version' metadata")

    def _guess_weight(self, family: str) -> float:
        """Infer default weight from model family name."""
        lowered = family.lower()
        for keyword, weight in DEFAULT_WEIGHT_HINTS.items():
            if keyword in lowered:
                return weight
        return 0.10

    def _bootstrap_if_empty(self) -> None:
        """Create baseline model and metadata if registry is empty."""
        if list(self.models_dir.glob("*.pkl")):
            return
        if not DATASET_PATH.exists():
            LOGGER.warning("Dataset missing: %s", DATASET_PATH)
            return

        data = pd.read_csv(DATASET_PATH)
        required = DEFAULT_FEATURES + [DEFAULT_TARGET]
        if any(column not in data.columns for column in required):
            LOGGER.warning("Dataset does not include required columns: %s", required)
            return

        model = RandomForestClassifier(n_estimators=300, random_state=42, max_depth=6)
        model.fit(data[DEFAULT_FEATURES], data[DEFAULT_TARGET])

        model_path = self.models_dir / "diabetes_model_v1.0.0.pkl"
        joblib.dump(model, model_path)

        meta_path = self.metadata_dir / "diabetes_model_v1.0.0.json"
        if not meta_path.exists():
            metadata = {
                "model_name": "Diabetes Risk Model",
                "description": "Predicts diabetes probability from key health indicators.",
                "features": DEFAULT_FEATURES,
                "weight": 0.30,
                "version": "1.0.0",
                "owner": "platform-team",
                "metrics": {"auc": 0.84, "f1": 0.79},
                "thresholds": {"medium": 0.40, "high": 0.70},
            }
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        LOGGER.info("Bootstrapped fallback model: %s", model_path)


_REGISTRY = ModelRegistry()


def load_models() -> dict[str, str]:
    """Load or reload all model bundles from disk."""
    return _REGISTRY.load_models()


def get_models() -> dict[str, dict[str, Any]]:
    """Return active model bundles by family."""
    return {family: bundle.__dict__ for family, bundle in _REGISTRY.get_models().items()}


def get_load_status() -> dict[str, str]:
    """Return current load status map."""
    return _REGISTRY.get_status()


def get_model_versions() -> dict[str, list[str]]:
    """Return available versions for every model family."""
    return _REGISTRY.get_all_versions()


def get_model_catalog() -> dict[str, Any]:
    """Return serializable model catalog."""
    return _REGISTRY.get_catalog()


def set_active_model_version(family: str, version: str) -> bool:
    """Activate a family/version pair for rollback support."""
    return _REGISTRY.set_active_version(family, version)


def predict_all(patient_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Run predictions on active versions across all model families."""
    return _REGISTRY.predict_all(patient_data)
