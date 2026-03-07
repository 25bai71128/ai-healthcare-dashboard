"""Weighted ensemble engine with score quality diagnostics."""

from __future__ import annotations

from statistics import mean
from typing import Any


def _risk_bucket(score_percent: float, medium_threshold: float = 40.0, high_threshold: float = 70.0) -> tuple[str, str]:
    """Map score percentage to risk label and UI color class."""
    if score_percent >= high_threshold:
        return "High", "danger"
    if score_percent >= medium_threshold:
        return "Medium", "warning"
    return "Low", "success"


def calculate_health_score(
    model_predictions: dict[str, dict[str, Any]],
    medium_threshold: float = 40.0,
    high_threshold: float = 70.0,
) -> dict[str, Any]:
    """Compute weighted health score and confidence diagnostics."""
    if not model_predictions:
        return {
            "overall_health_score": 0.0,
            "risk_level": "Low",
            "risk_class": "success",
            "weighted_probability": 0.0,
            "mean_model_probability": 0.0,
            "prediction_spread": 0.0,
            "model_count": 0,
        }

    weighted_sum = 0.0
    weight_total = 0.0
    probabilities: list[float] = []

    for payload in model_predictions.values():
        probability = float(payload.get("probability", 0.0))
        weight = float(payload.get("weight", 0.0))

        weighted_sum += probability * weight
        weight_total += weight
        probabilities.append(probability)

    weighted_probability = (weighted_sum / weight_total) if weight_total > 0 else mean(probabilities)
    weighted_probability = max(0.0, min(1.0, weighted_probability))

    overall_health_score = round(weighted_probability * 100, 2)
    risk_level, risk_class = _risk_bucket(overall_health_score, medium_threshold, high_threshold)

    prediction_spread = round((max(probabilities) - min(probabilities)) * 100, 2) if len(probabilities) > 1 else 0.0

    return {
        "overall_health_score": overall_health_score,
        "weighted_probability": round(weighted_probability, 4),
        "mean_model_probability": round(mean(probabilities), 4),
        "prediction_spread": prediction_spread,
        "model_count": len(probabilities),
        "risk_level": risk_level,
        "risk_class": risk_class,
    }
