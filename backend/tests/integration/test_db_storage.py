from app.core.config import get_settings
from tests.conftest import drain, login, upload


def test_pipeline_and_document_download_with_database_storage(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_backend", "db")
    h = login(client)
    r = upload(client, h, "S01")
    assert r.status_code == 201
    drain()
    inv_id = r.json()["invoice_id"]
    d = client.get(f"/api/invoices/{inv_id}", headers=h).json()
    assert d["status"] == "READY_FOR_APPROVAL"
    pdf = client.get(f"/api/invoices/{inv_id}/document", headers=h)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    assert client.get("/api/health/ready").json()["storage_backend"] == "db"
