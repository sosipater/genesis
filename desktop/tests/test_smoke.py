from pathlib import Path

from fastapi.testclient import TestClient

from desktop.app.sync.api import create_app


def test_health_smoke() -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=root / "desktop" / "tests" / "tmp_smoke.db")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

