"""
Phase 2 smoke tests: confirm the skeleton actually runs and the
request -> background-task -> state flow works, independent of any real
simulation logic (that lands in Phase 3).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_run_returns_queued_run():
    response = client.post(
        "/simulation/run",
        json={"num_stores": 3, "num_steps": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("queued", "running")
    assert "run_id" in body


def test_get_run_status_after_start():
    start = client.post("/simulation/run", json={"num_stores": 2, "num_steps": 1})
    run_id = start.json()["run_id"]

    status = client.get(f"/simulation/{run_id}")
    assert status.status_code == 200
    assert status.json()["run_id"] == run_id


def test_get_unknown_run_is_404():
    response = client.get("/simulation/does-not-exist")
    assert response.status_code == 404


def test_network_metrics_shape():
    start = client.post(
        "/simulation/run",
        json={"num_suppliers": 1, "num_distribution_centers": 1, "num_stores": 5, "num_steps": 1},
    )
    run_id = start.json()["run_id"]

    metrics = client.get(f"/analytics/{run_id}/network-metrics")
    assert metrics.status_code == 200
    assert metrics.json()["node_count"] == 7


def test_state_endpoint_available_immediately_and_returns_snapshot_shape():
    start = client.post(
        "/simulation/run",
        json={"num_suppliers": 1, "num_distribution_centers": 1, "num_stores": 3, "num_steps": 5},
    )
    run_id = start.json()["run_id"]

    state_response = client.get(f"/simulation/{run_id}/state")
    assert state_response.status_code == 200
    body = state_response.json()
    assert body["run_id"] == run_id
    assert set(body["inventory_levels"].keys()) == {"store_0", "store_1", "store_2", "dc_0", "supplier_0"}
    assert isinstance(body["stockouts"], list)


def test_state_endpoint_unknown_run_is_404():
    response = client.get("/simulation/does-not-exist/state")
    assert response.status_code == 404
