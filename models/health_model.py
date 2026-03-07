"""Model training and loading utilities for health risk prediction."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "health_data.csv"
MODEL_PATH = Path(__file__).resolve().parent / "health_risk_model.joblib"
FEATURE_COLUMNS = ["age", "blood_pressure", "cholesterol"]
TARGET_COLUMN = "diabetes_risk"


def train_model():
    """Train a RandomForest model and persist it to disk."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH)
    missing = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN] if col not in data.columns]
    if missing:
        raise ValueError(f"Missing expected column(s) in dataset: {', '.join(missing)}")

    x_train = data[FEATURE_COLUMNS]
    y_train = data[TARGET_COLUMN]

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        max_depth=6,
    )
    model.fit(x_train, y_train)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return model


def load_model():
    """Load a persisted model, or train one if missing."""
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return train_model()
