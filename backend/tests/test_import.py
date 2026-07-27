from __future__ import annotations

from datetime import date, timedelta

from conftest import auth_headers, make_account, register_user

from app.services.imports import parse_amount, parse_ofx, parse_qif


def test_parse_amount_formats():
    assert parse_amount("-12,50") == -1250
    assert parse_amount("1.234,56") == 123456
    assert parse_amount("1,234.56") == 123456
    assert parse_amount("(45.00)") == -4500
    assert parse_amount("CHF 99.90") == 9990
    assert parse_amount("1'250.00") == 125000


def test_parse_qif():
    sample = "!Type:Bank\nD15.06.2026\nT-12.50\nPMigros\nMEinkauf\n^\nD16.06.2026\nT2500.00\nPLohn\n^\n"
    rows = parse_qif(sample)
    assert len(rows) == 2
    assert rows[0] == {"date": "2026-06-15", "amount": "-12.50", "payee": "Migros", "notes": "Einkauf"}
    assert rows[1]["amount"] == "2500.00"


def test_parse_ofx():
    sample = (
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260610<TRNAMT>-25.00<FITID>1<NAME>Coop Pronto<MEMO>Tanken</STMTTRN>"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260611<TRNAMT>100.00<FITID>2<NAME>Einzahlung</STMTTRN>"
        "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    )
    rows = parse_ofx(sample)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-06-10"
    assert rows[0]["amount"] == "-25.00"
    assert rows[0]["payee"] == "Coop Pronto"
    assert rows[1]["amount"] == "100.00"


async def test_csv_import_mapping_and_dedupe(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)

    csv_content = "Datum;Betrag;Empfänger\n15.06.2026;-12,50;Migros\n16.06.2026;-8,90;Coop\n"
    files = {"file": ("export.csv", csv_content.encode("utf-8"), "text/csv")}
    r = await client.post("/api/v1/import/preview", files=files, headers=h)
    assert r.status_code == 200, r.text
    prev = r.json()
    assert prev["format"] == "csv"
    assert "Betrag" in prev["columns"]
    assert prev["row_count"] == 2

    commit = {
        "cache_id": prev["cache_id"],
        "account_id": acc["id"],
        "mapping": {"date": "Datum", "amount": "Betrag", "payee": "Empfänger"},
    }
    r = await client.post("/api/v1/import/commit", json=commit, headers=h)
    assert r.json() == {"imported": 2, "duplicates_skipped": 0, "errors": 0}

    r = await client.post("/api/v1/import/commit", json=commit, headers=h)
    assert r.json()["imported"] == 0
    assert r.json()["duplicates_skipped"] == 2

    txns = (await client.get("/api/v1/transactions", headers=h)).json()
    assert txns["total"] == 2
    migros = next(t for t in txns["items"] if t["payee"] == "Migros")
    assert migros["amount"] == -1250
    assert migros["date"] == "2026-06-15"


async def test_fuzzy_duplicate_detection(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)
    d = date(2026, 6, 20)

    r = await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": d.isoformat(), "amount": -1250, "payee": "Migros Basel"},
        headers=h,
    )
    assert r.status_code == 201

    # Same amount, one day later, slightly different payee casing/spacing -> fuzzy duplicate
    csv_content = "date,amount,payee\n{},-12.50,MIGROS  Basel\n".format(
        (d + timedelta(days=1)).strftime("%d.%m.%Y")
    )
    files = {"file": ("export.csv", csv_content.encode("utf-8"), "text/csv")}
    prev = (await client.post("/api/v1/import/preview", files=files, headers=h)).json()
    r = await client.post(
        "/api/v1/import/commit",
        json={
            "cache_id": prev["cache_id"],
            "account_id": acc["id"],
            "mapping": {"date": "date", "amount": "amount", "payee": "payee"},
        },
        headers=h,
    )
    assert r.json()["duplicates_skipped"] == 1
    assert r.json()["imported"] == 0


async def test_ofx_upload_roundtrip(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)

    ofx = (
        "OFXHEADER:100\n\n<OFX><BANKTRANLIST>"
        "<STMTTRN><DTPOSTED>20260701<TRNAMT>-42.00<NAME>SBB</STMTTRN>"
        "</BANKTRANLIST></OFX>"
    )
    files = {"file": ("konto.ofx", ofx.encode("utf-8"), "application/x-ofx")}
    prev = (await client.post("/api/v1/import/preview", files=files, headers=h)).json()
    assert prev["format"] == "ofx"
    r = await client.post(
        "/api/v1/import/commit", json={"cache_id": prev["cache_id"], "account_id": acc["id"]}, headers=h
    )
    assert r.json()["imported"] == 1
    txns = (await client.get("/api/v1/transactions", headers=h)).json()
    assert txns["items"][0]["payee"] == "SBB"
    assert txns["items"][0]["amount"] == -4200
