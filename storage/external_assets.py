"""Utilities for fetching large runtime artifacts from external object storage."""

from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

LOGGER = logging.getLogger(__name__)
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in TRUTHY_VALUES)


def _filename_from_url(url: str, fallback: str) -> str:
    path = urlparse(url).path
    name = Path(path).name
    return name or fallback


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response, destination.open("wb") as file_obj:
        shutil.copyfileobj(response, file_obj)


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as zip_file:
        for member in zip_file.infolist():
            candidate = (destination / member.filename).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise ValueError(f"Unsafe zip member path: {member.filename}")
        zip_file.extractall(destination)


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path) as tar_file:
        for member in tar_file.getmembers():
            candidate = (destination / member.name).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise ValueError(f"Unsafe tar member path: {member.name}")
        tar_file.extractall(destination)


def _extract_archive(archive_path: Path, destination: Path) -> None:
    name = archive_path.name.lower()
    if name.endswith(".zip"):
        _safe_extract_zip(archive_path, destination)
        return
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        _safe_extract_tar(archive_path, destination)
        return
    raise ValueError(f"Unsupported archive format: {archive_path.name}")


def _clear_directory(directory: Path) -> None:
    if not directory.exists():
        return
    for item in directory.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _sync_archive(url: str, destination: Path, force: bool) -> bool:
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()) and not force:
        return False

    if force:
        _clear_directory(destination)

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_name = _filename_from_url(url, "artifacts.zip")
        archive_path = Path(temp_dir) / archive_name
        _download(url, archive_path)
        _extract_archive(archive_path, destination)
    return True


def _sync_file(url: str, destination: Path, force: bool) -> bool:
    if destination.exists() and not force:
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / destination.name
        _download(url, temp_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_file, destination)
    return True


def sync_external_artifacts(base_dir: Path, logger: logging.Logger | None = None) -> list[str]:
    """Fetch model/data artifacts when external storage URLs are configured.

    Environment variables:
    - MODEL_ARCHIVE_URL: archive containing model .pkl files for models/trained_models/
    - METADATA_ARCHIVE_URL: archive containing model metadata JSON files for models/metadata/
    - DATA_ARCHIVE_URL: archive containing data/ artifacts
    - DATASET_URL: direct URL for data/health_data.csv
    - MODEL_FILE_URL: direct URL for a single model file (name from MODEL_FILE_NAME or URL)
    - METADATA_FILE_URL: direct URL for a single metadata file (name from METADATA_FILE_NAME or URL)
    - ACTIVE_VERSIONS_URL: direct URL for models/active_versions.json
    - FORCE_EXTERNAL_ASSET_SYNC=true: overwrite existing local artifacts
    - SKIP_EXTERNAL_ASSET_SYNC=true: disable sync entirely
    """
    log = logger or LOGGER
    if _is_truthy(os.environ.get("SKIP_EXTERNAL_ASSET_SYNC")):
        return []

    force = _is_truthy(os.environ.get("FORCE_EXTERNAL_ASSET_SYNC"))
    synced: list[str] = []

    archive_targets = [
        ("MODEL_ARCHIVE_URL", base_dir / "models" / "trained_models"),
        ("METADATA_ARCHIVE_URL", base_dir / "models" / "metadata"),
        ("DATA_ARCHIVE_URL", base_dir / "data"),
    ]

    for env_name, destination in archive_targets:
        url = os.environ.get(env_name, "").strip()
        if not url:
            continue
        try:
            if _sync_archive(url, destination, force=force):
                synced.append(env_name)
        except Exception as exc:  # pragma: no cover - network/external dependencies
            log.warning("Failed to sync %s: %s", env_name, exc)

    dataset_url = os.environ.get("DATASET_URL", "").strip()
    if dataset_url:
        try:
            target = base_dir / "data" / "health_data.csv"
            if _sync_file(dataset_url, target, force=force):
                synced.append("DATASET_URL")
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to sync DATASET_URL: %s", exc)

    model_file_url = os.environ.get("MODEL_FILE_URL", "").strip()
    if model_file_url:
        model_name = os.environ.get("MODEL_FILE_NAME", "").strip() or _filename_from_url(model_file_url, "external_model.pkl")
        target = base_dir / "models" / "trained_models" / model_name
        try:
            if _sync_file(model_file_url, target, force=force):
                synced.append("MODEL_FILE_URL")
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to sync MODEL_FILE_URL: %s", exc)

    metadata_file_url = os.environ.get("METADATA_FILE_URL", "").strip()
    if metadata_file_url:
        metadata_name = os.environ.get("METADATA_FILE_NAME", "").strip() or _filename_from_url(
            metadata_file_url,
            "external_model.json",
        )
        target = base_dir / "models" / "metadata" / metadata_name
        try:
            if _sync_file(metadata_file_url, target, force=force):
                synced.append("METADATA_FILE_URL")
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to sync METADATA_FILE_URL: %s", exc)

    active_versions_url = os.environ.get("ACTIVE_VERSIONS_URL", "").strip()
    if active_versions_url:
        target = base_dir / "models" / "active_versions.json"
        try:
            if _sync_file(active_versions_url, target, force=force):
                synced.append("ACTIVE_VERSIONS_URL")
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to sync ACTIVE_VERSIONS_URL: %s", exc)

    return synced
