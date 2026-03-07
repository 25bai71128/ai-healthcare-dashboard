"""Basic integration tests for AI healthcare platform."""

from app import app


def test_home_page_loads():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"AI Healthcare Decision Support Platform" in response.data


def test_api_predict_sync():
    client = app.test_client()
    response = client.post(
        "/api/predict",
        json={"age": 45, "blood_pressure": 140, "cholesterol": 220},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "health_score" in payload["data"]


def test_api_predict_async_and_job_status():
    client = app.test_client()
    response = client.post(
        "/api/predict?async=true",
        json={"age": 48, "blood_pressure": 142, "cholesterol": 230},
    )
    assert response.status_code == 202
    payload = response.get_json()
    job_id = payload["job_id"]

    job_status = client.get(f"/api/jobs/{job_id}")
    assert job_status.status_code == 200
    assert job_status.get_json()["ok"] is True


def test_model_catalog_endpoint():
    client = app.test_client()
    response = client.get("/api/models")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "catalog" in payload["data"]
