"""Reinforcement learning utilities for treatment strategy optimization.

This is a simulation-based RL module intended for prototyping and UI demos.
It MUST NOT be used as clinical decision logic. The environment dynamics are
synthetic and the "treatments" are abstract actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


def _clip01(value: float) -> float:
    return float(np.clip(float(value), 0.0, 1.0))


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
        if np.isfinite(parsed):
            return parsed
    except Exception:
        pass
    return None


def estimate_health_risk(patient_metrics: dict[str, Any]) -> float:
    """Map vitals-like inputs to a crude risk score in [0, 1].

    Supported keys (case-insensitive; any missing values are ignored):
    - systolic, diastolic, glucose, cholesterol, heartRate, age
    """

    def pick(*names: str) -> float | None:
        lowered = {str(k).lower(): v for k, v in (patient_metrics or {}).items()}
        for name in names:
            if name.lower() in lowered:
                return _safe_float(lowered[name.lower()])
        return None

    systolic = pick("systolic", "blood_pressure", "bp_systolic")
    diastolic = pick("diastolic", "bp_diastolic")
    glucose = pick("glucose", "blood_glucose")
    cholesterol = pick("cholesterol", "chol")
    heart_rate = pick("heartrate", "heart_rate", "hr")
    age = pick("age")

    components: list[float] = []
    if systolic is not None:
        components.append(_clip01((systolic - 120.0) / 60.0))
    if diastolic is not None:
        components.append(_clip01((diastolic - 80.0) / 40.0))
    if glucose is not None:
        components.append(_clip01((glucose - 100.0) / 150.0))
    if cholesterol is not None:
        components.append(_clip01((cholesterol - 180.0) / 120.0))
    if heart_rate is not None:
        components.append(_clip01((heart_rate - 80.0) / 60.0))
    if age is not None:
        components.append(_clip01((age - 45.0) / 45.0))

    if not components:
        return 0.5

    # A small baseline ensures "unknown" isn't treated as low-risk.
    return _clip01(0.10 + 0.90 * float(np.mean(components)))


@dataclass(frozen=True)
class TreatmentRecommendation:
    action: str
    expected_outcome_score: float
    risk_before: float
    risk_after: float
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_treatment": self.action,
            "expected_outcome_score": self.expected_outcome_score,
            "risk_before": self.risk_before,
            "risk_after": self.risk_after,
            "notes": self.notes,
        }


class TreatmentRLEnvironment:
    """Synthetic environment where state is a continuous risk score in [0, 1]."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng

    def reset(self) -> float:
        # Start mostly in the mid-range; bias toward moderate risk.
        return float(self.rng.beta(2.2, 2.2))

    def step(self, risk: float, action_idx: int) -> tuple[float, float, bool]:
        """Apply an action and return (next_risk, reward, done)."""

        risk = _clip01(risk)

        # Effects/costs are abstract and calibrated for stability, not realism.
        action_effects = np.array([0.01, 0.03, 0.05, 0.07, 0.09], dtype=float)
        action_costs = np.array([0.00, 0.02, 0.05, 0.07, 0.10], dtype=float)

        action_effect = float(action_effects[int(action_idx)])
        action_cost = float(action_costs[int(action_idx)])

        # Natural drift slightly increases risk; noise makes transitions stochastic.
        drift = float(self.rng.normal(loc=0.008, scale=0.010))
        noise = float(self.rng.normal(loc=0.0, scale=0.020))

        # "Over-treatment" penalty when risk is already low.
        overtreatment_penalty = 0.0
        if risk < 0.25 and action_idx >= 2:
            overtreatment_penalty = 0.08

        next_risk = _clip01(risk + drift + noise - action_effect + overtreatment_penalty)

        improvement = risk - next_risk
        reward = (improvement * 10.0) - action_cost - (0.5 * overtreatment_penalty)

        done = bool(next_risk < 0.18)
        return next_risk, float(reward), done

    def expected_next_risk(self, risk: float, action_idx: int) -> float:
        """Deterministic estimate for UI-facing 'expected outcome'."""

        risk = _clip01(risk)
        action_effects = np.array([0.01, 0.03, 0.05, 0.07, 0.09], dtype=float)
        drift = 0.008
        overtreatment_penalty = 0.08 if (risk < 0.25 and action_idx >= 2) else 0.0
        return _clip01(risk + drift - float(action_effects[int(action_idx)]) + overtreatment_penalty)


class TreatmentRLAgent:
    """Tabular Q-learning agent over discretized risk bins."""

    def __init__(
        self,
        *,
        actions: list[str] | None = None,
        n_risk_bins: int = 12,
        alpha: float = 0.20,
        gamma: float = 0.92,
        epsilon: float = 0.25,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.05,
        random_state: int = 42,
    ) -> None:
        self.actions = actions or [
            "monitor_only",
            "lifestyle_adjustment",
            "medication_low_intensity",
            "medication_high_intensity",
            "specialist_referral",
        ]
        self.n_risk_bins = int(max(4, n_risk_bins))
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.min_epsilon = float(min_epsilon)

        self.rng = np.random.default_rng(int(random_state))
        self.env = TreatmentRLEnvironment(self.rng)
        self.q_table = np.zeros((self.n_risk_bins, len(self.actions)), dtype=float)
        self.trained_episodes = 0

    def _discretize(self, risk: float) -> int:
        risk = _clip01(risk)
        idx = int(risk * self.n_risk_bins)
        return int(np.clip(idx, 0, self.n_risk_bins - 1))

    def _choose_action(self, state_idx: int) -> int:
        if float(self.rng.random()) < self.epsilon:
            return int(self.rng.integers(0, len(self.actions)))
        return int(np.argmax(self.q_table[state_idx]))

    def train(self, *, episodes: int = 1500, max_steps: int = 24) -> None:
        episodes = int(max(1, episodes))
        max_steps = int(max(1, max_steps))

        for _ in range(episodes):
            risk = self.env.reset()
            state = self._discretize(risk)
            done = False

            for _step in range(max_steps):
                action = self._choose_action(state)
                next_risk, reward, done = self.env.step(risk, action)
                next_state = self._discretize(next_risk)

                best_next = float(np.max(self.q_table[next_state]))
                td_target = reward + (self.gamma * best_next)
                td_error = td_target - float(self.q_table[state, action])
                self.q_table[state, action] = float(self.q_table[state, action] + self.alpha * td_error)

                risk = next_risk
                state = next_state
                if done:
                    break

            self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
            self.trained_episodes += 1

    def recommend(self, patient_metrics: dict[str, Any]) -> TreatmentRecommendation:
        risk_before = estimate_health_risk(patient_metrics)
        state = self._discretize(risk_before)
        action_idx = int(np.argmax(self.q_table[state]))
        action = self.actions[action_idx]

        risk_after = float(self.env.expected_next_risk(risk_before, action_idx))
        expected_outcome_score = round((1.0 - risk_after) * 100.0, 2)

        return TreatmentRecommendation(
            action=action,
            expected_outcome_score=float(expected_outcome_score),
            risk_before=round(float(risk_before), 4),
            risk_after=round(float(risk_after), 4),
            notes=(
                "Simulation-only RL policy. Do not interpret as medical advice; "
                "use for prototyping and consult a clinician for any treatment decisions."
            ),
        )


_DEFAULT_AGENT: TreatmentRLAgent | None = None


def get_default_agent() -> TreatmentRLAgent:
    """Return a lazily trained default agent (cached in-process)."""

    global _DEFAULT_AGENT
    if _DEFAULT_AGENT is None:
        agent = TreatmentRLAgent()
        # Keep runtime predictable: train enough to yield a stable policy, but fast.
        agent.train(episodes=1200, max_steps=22)
        _DEFAULT_AGENT = agent
    return _DEFAULT_AGENT

