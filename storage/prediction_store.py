"""Persistence layer for prediction records with SQLite default and PostgreSQL optional."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psycopg2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psycopg2 = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IS_VERCEL = os.environ.get("VERCEL", "").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_SQLITE_PATH = Path(
    os.environ.get(
        "PREDICTIONS_SQLITE_PATH",
        "/tmp/ai_healthcare_project/data/predictions.db" if IS_VERCEL else str(PROJECT_ROOT / "data" / "predictions.db"),
    )
)


@dataclass
class PredictionRecord:
    """Serializable record structure for persisted predictions."""

    request_id: str
    patient_data: dict[str, Any]
    model_predictions: dict[str, Any]
    health_score: dict[str, Any]
    monitoring: dict[str, Any]
    report_file: str
    timestamp: str


class PredictionStore:
    """Prediction repository supporting SQLite and optional PostgreSQL."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", "")
        self.use_postgres = self.database_url.startswith("postgresql") and psycopg2 is not None
        self.sqlite_path = DEFAULT_SQLITE_PATH
        try:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback = Path("/tmp/ai_healthcare_project/data/predictions.db")
            fallback.parent.mkdir(parents=True, exist_ok=True)
            self.sqlite_path = fallback
        self._init_db()

    def _connect_sqlite(self) -> sqlite3.Connection:
        """Open sqlite connection with row factory."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_postgres(self):
        """Open postgres connection when configured and driver available."""
        if not self.use_postgres:
            raise RuntimeError("PostgreSQL connection is not configured")
        return psycopg2.connect(self.database_url)

    def _init_db(self) -> None:
        """Create storage tables."""
        if self.use_postgres:
            with self._connect_postgres() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS predictions (
                            id SERIAL PRIMARY KEY,
                            request_id TEXT NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            patient_data JSONB NOT NULL,
                            model_predictions JSONB NOT NULL,
                            health_score JSONB NOT NULL,
                            monitoring JSONB NOT NULL,
                            report_file TEXT NOT NULL
                        )
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS case_notes (
                            id SERIAL PRIMARY KEY,
                            request_id TEXT NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            author TEXT NOT NULL,
                            note TEXT NOT NULL,
                            tags JSONB NOT NULL
                        )
                        """
                    )
                conn.commit()
            return

        with self._connect_sqlite() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    patient_data TEXT NOT NULL,
                    model_predictions TEXT NOT NULL,
                    health_score TEXT NOT NULL,
                    monitoring TEXT NOT NULL,
                    report_file TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS case_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    author TEXT NOT NULL,
                    note TEXT NOT NULL,
                    tags TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_prediction(self, record: PredictionRecord) -> None:
        """Persist a prediction record."""
        if self.use_postgres:
            with self._connect_postgres() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO predictions
                        (request_id, created_at, patient_data, model_predictions, health_score, monitoring, report_file)
                        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                        """,
                        (
                            record.request_id,
                            record.timestamp,
                            json.dumps(record.patient_data),
                            json.dumps(record.model_predictions),
                            json.dumps(record.health_score),
                            json.dumps(record.monitoring),
                            record.report_file,
                        ),
                    )
                conn.commit()
            return

        with self._connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO predictions
                (request_id, created_at, patient_data, model_predictions, health_score, monitoring, report_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
                    record.timestamp,
                    json.dumps(record.patient_data),
                    json.dumps(record.model_predictions),
                    json.dumps(record.health_score),
                    json.dumps(record.monitoring),
                    record.report_file,
                ),
            )
            conn.commit()

    def fetch_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        """Fetch recent prediction rows for dashboard/API history."""
        if self.use_postgres:
            with self._connect_postgres() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT request_id, created_at, patient_data, model_predictions, health_score, monitoring, report_file
                        FROM predictions
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
            return [
                {
                    "request_id": row[0],
                    "created_at": str(row[1]),
                    "patient_data": row[2],
                    "model_predictions": row[3],
                    "health_score": row[4],
                    "monitoring": row[5],
                    "report_file": row[6],
                }
                for row in rows
            ]

        with self._connect_sqlite() as conn:
            rows = conn.execute(
                """
                SELECT request_id, created_at, patient_data, model_predictions, health_score, monitoring, report_file
                FROM predictions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "request_id": row["request_id"],
                    "created_at": row["created_at"],
                    "patient_data": json.loads(row["patient_data"]),
                    "model_predictions": json.loads(row["model_predictions"]),
                    "health_score": json.loads(row["health_score"]),
                    "monitoring": json.loads(row["monitoring"]),
                    "report_file": row["report_file"],
                }
            )
        return result

    def monitoring_summary(self) -> dict[str, Any]:
        """Aggregate lightweight monitoring metrics from recent records."""
        rows = self.fetch_recent(limit=200)
        if not rows:
            return {
                "samples": 0,
                "drift_rate": 0.0,
                "avg_health_score": 0.0,
            }

        drift_count = 0
        scores: list[float] = []
        for row in rows:
            monitoring = row.get("monitoring", {})
            if monitoring.get("drift_detected"):
                drift_count += 1
            scores.append(float(row.get("health_score", {}).get("overall_health_score", 0.0)))

        avg_score = sum(scores) / len(scores) if scores else 0.0
        return {
            "samples": len(rows),
            "drift_rate": round((drift_count / len(rows)) * 100, 2),
            "avg_health_score": round(avg_score, 2),
        }

    def save_case_note(self, request_id: str, author: str, note: str, tags: list[str]) -> None:
        """Persist clinician annotation for a specific case/request."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        if self.use_postgres:
            with self._connect_postgres() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO case_notes
                        (request_id, created_at, author, note, tags)
                        VALUES (%s, %s, %s, %s, %s::jsonb)
                        """,
                        (request_id, timestamp, author, note, json.dumps(tags)),
                    )
                conn.commit()
            return

        with self._connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO case_notes
                (request_id, created_at, author, note, tags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (request_id, timestamp, author, note, json.dumps(tags)),
            )
            conn.commit()

    def fetch_case_notes(self, request_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch clinician notes and tags by request id."""
        if self.use_postgres:
            with self._connect_postgres() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT request_id, created_at, author, note, tags
                        FROM case_notes
                        WHERE request_id = %s
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (request_id, limit),
                    )
                    rows = cursor.fetchall()
            return [
                {
                    "request_id": row[0],
                    "created_at": str(row[1]),
                    "author": row[2],
                    "note": row[3],
                    "tags": row[4],
                }
                for row in rows
            ]

        with self._connect_sqlite() as conn:
            rows = conn.execute(
                """
                SELECT request_id, created_at, author, note, tags
                FROM case_notes
                WHERE request_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (request_id, limit),
            ).fetchall()

        return [
            {
                "request_id": row["request_id"],
                "created_at": row["created_at"],
                "author": row["author"],
                "note": row["note"],
                "tags": json.loads(row["tags"]),
            }
            for row in rows
        ]


def build_record(
    request_id: str,
    patient_data: dict[str, Any],
    model_predictions: dict[str, Any],
    health_score: dict[str, Any],
    monitoring: dict[str, Any],
    report_file: str,
) -> PredictionRecord:
    """Build a timestamped prediction record."""
    return PredictionRecord(
        request_id=request_id,
        patient_data=patient_data,
        model_predictions=model_predictions,
        health_score=health_score,
        monitoring=monitoring,
        report_file=report_file,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
