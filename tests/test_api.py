# The HTTP layer: guards, validation, exports, PDFs.
import core
from conftest import fee_of


def test_foreign_host_is_refused(client):
    """DNS rebinding: the attacker's own domain resolves to 127.0.0.1."""
    r = client.get("/api/apartments", headers={"Host": "evil.example:5050"})
    assert r.status_code == 403
    assert client.get("/api/apartments", headers={"Host": "localhost:5050"}).status_code == 200
    assert client.get("/api/apartments", headers={"Host": "127.0.0.1:5050"}).status_code == 200


def test_cross_site_write_is_refused(client):
    r = client.post("/api/apartments", json={"number": "1"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/apartments", json={"number": "1"},
                    headers={"Origin": "http://localhost:5050"})
    assert r.status_code == 200


def test_names_are_required(client):
    apt = client.post("/api/apartments", json={"number": "1"}).get_json()["id"]
    r = client.post("/api/residents", json={"apt_id": apt, "full_name": "  "})
    assert r.status_code == 400 and "Три имена" in r.get_json()["error"]
    r = client.post(f"/api/apartments/{apt}/owner", json={"full_name": ""})
    assert r.status_code == 400
    r = client.post("/api/chips", json={"apt_id": apt, "chip_number": ""})
    assert r.status_code == 400


def test_unknown_ids_answer_404_not_500(client):
    assert client.put("/api/finance/fees/999", json={"status": "paid"}).status_code == 404
    assert client.delete("/api/finance/advance-payments/999").status_code == 404
    assert client.delete("/api/finance/transactions/999").status_code == 404
    assert client.delete("/api/apartments/999").status_code == 404
    assert client.get("/api/apartments/999/detail").status_code == 404
    assert client.post("/api/finance/fees/999/pay",
                       json={"amount": 5, "date": "2026-01-01"}).status_code == 404


def test_duplicate_apartment_number_is_a_400(client):
    client.post("/api/apartments", json={"number": "1"})
    r = client.post("/api/apartments", json={"number": "1"})
    assert r.status_code == 400 and "номер" in r.get_json()["error"]


def test_owner_lives_here_through_the_api(client):
    apt = client.post("/api/apartments", json={"number": "1"}).get_json()["id"]
    client.post(f"/api/apartments/{apt}/owner",
                json={"full_name": "Иван Иванов", "phone": "0888", "lives_here": True})
    d = client.get(f"/api/apartments/{apt}/detail").get_json()
    assert d["owner_is_resident"] is True
    assert [(r["full_name"], r["role"]) for r in d["residents"]] == [("Иван Иванов", "owner")]


def test_transaction_date_is_validated_and_sets_the_period(client):
    r = client.post("/api/finance/transactions",
                    json={"type": "expense", "amount": 10, "date": "13.11.2026"})
    assert r.status_code == 400
    r = client.post("/api/finance/transactions",
                    json={"type": "expense", "amount": -10, "date": "2026-11-13"})
    assert r.status_code == 400
    r = client.post("/api/finance/transactions",
                    json={"type": "expense", "amount": 10, "date": "2026-11-13",
                          "period": "2026-03"})
    assert r.status_code == 200
    rows = client.get("/api/finance/transactions?period=2026-11").get_json()
    assert len(rows) == 1 and rows[0]["period"] == "2026-11"


def test_pay_and_documents(client, building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    fid = fee_of(a1, "2026-01")["id"]

    # No payment yet → no receipt.
    assert client.post(f"/api/reports/generate-receipt/{fid}").status_code == 400

    r = client.post(f"/api/finance/fees/{fid}/pay",
                    json={"amount": "23,00", "date": "2026-01-10", "payment_method": "cash"})
    assert r.status_code == 200 and r.get_json()["applied"] == 23.0

    for url in (f"/api/reports/generate-receipt/{fid}",
                f"/api/reports/generate-statement/{a1}"):
        r = client.post(url)
        assert r.status_code == 200, r.get_json()
        pdf = client.get("/api/reports/view/" + r.get_json()["filename"])
        assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"

    st = client.get(f"/api/apartments/{a1}/statement").get_json()
    assert (st["total_billed"], st["total_paid"], st["total_owed"]) == (23.0, 23.0, 0.0)


def test_csv_export_opens_in_bulgarian_excel(client, building):
    core.generate_monthly_fees("2026-01")
    r = client.get("/api/export/fees/2026-01.csv")
    assert r.status_code == 200
    text = r.data.decode("utf-8")
    assert text.startswith("﻿")                 # BOM → Excel reads Cyrillic
    lines = text.strip().split("\r\n")
    assert lines[0].split(";")[0].lstrip("﻿") == "Апартамент"
    assert "23,00" in lines[1]                       # decimal comma
    assert client.get("/api/export/fees/2026-13.csv").status_code == 400


def test_import_apartments(client):
    rows = [
        {"number": "1", "floor": 1, "area_m2": "65,5", "owner_name": "Иван Иванов",
         "owner_lives_here": True},
        {"number": "2"},
        {"number": "1"},                              # duplicate inside the file
    ]
    r = client.post("/api/apartments/import", json={"rows": rows}).get_json()
    assert r == {"created": 2, "skipped": ["1"]}
    apts = client.get("/api/apartments").get_json()
    assert [(a["number"], a["residents_count"]) for a in apts] == [("1", 1), ("2", 0)]
    assert apts[0]["area_m2"] == 65.5


def test_archive_flow_through_the_api(client, building):
    a1, _ = building
    core.generate_monthly_fees("2026-01")
    assert client.delete(f"/api/apartments/{a1}").get_json()["result"] == "archived"
    assert len(client.get("/api/apartments").get_json()) == 1
    assert len(client.get("/api/apartments?archived=1").get_json()) == 2
    client.post(f"/api/apartments/{a1}/restore")
    assert len(client.get("/api/apartments").get_json()) == 2


def test_backups_api(client):
    name = client.post("/api/backups").get_json()["name"]
    assert name in [f["name"] for f in client.get("/api/backups").get_json()["files"]]
    assert client.get(f"/api/backups/{name}/download").status_code == 200
    assert client.get("/api/backups/..%2Fetazna.db/download").status_code == 404
    assert client.post(f"/api/backups/{name}/restore").status_code == 200


def test_ping_identifies_the_program(client):
    j = client.get("/api/ping").get_json()
    assert j["app"] == "es-menidzhar" and j["version"] == core.__version__
