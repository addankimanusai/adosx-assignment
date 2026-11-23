from decimal import Decimal
import pytest
from reconcile.compare import compare_ledgers
from reconcile.importer import normalize_ref


def test_missing_in_b():
    a = {
        "REC-1015": {
            "record_id": "REC-1015",
            "total_value": Decimal("1500.00"),
            "location_id": "LOC-103",
            "event_date": "2026-03-15",
            "state": "CONFIRMED",
        }
    }
    b = []
    res = compare_ledgers(a, b)
    assert len(res) == 1
    assert res[0]["reason"] == "MISSING_IN_B"
    assert res[0]["record_id"] == "REC-1015"
    assert res[0]["a_value"] == Decimal("1500.00")
    assert res[0]["b_value"] is None


def test_orphan_in_b():
    a = {}
    b = [
        {
            "entry_id": "ENT/2026/4901",
            "record_ref": "REC-1999",
            "value": Decimal("45000.00"),
            "location_id": "LOC-102",
            "recorded_on": "2026-04-01",
        }
    ]
    res = compare_ledgers(a, b)
    assert len(res) == 1
    assert res[0]["reason"] == "ORPHAN_IN_B"
    assert res[0]["record_id"] == "REC-1999"
    assert res[0]["location"] == "LOC-102"
    assert res[0]["a_value"] is None
    assert res[0]["b_value"] == Decimal("45000.00")


def test_duplicate_in_b():
    a = {
        "REC-1042": {
            "record_id": "REC-1042",
            "total_value": Decimal("112837.06"),
            "location_id": "LOC-101",
            "event_date": "2026-03-20",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4042",
            "record_ref": "REC-1042",
            "value": Decimal("112837.06"),
            "location_id": "LOC-101",
            "recorded_on": "2026-03-20",
        },
        {
            "entry_id": "ENT/2026/4043",
            "record_ref": "REC-1042",
            "value": Decimal("112837.06"),
            "location_id": "LOC-101",
            "recorded_on": "2026-03-20",
        },
    ]
    res = compare_ledgers(a, b)
    assert len(res) == 1
    assert res[0]["reason"] == "DUPLICATE_IN_B"
    assert res[0]["record_id"] == "REC-1042"
    assert res[0]["a_value"] == Decimal("112837.06")
    assert res[0]["b_value"] == Decimal("225674.12")
    assert res[0]["difference"] == Decimal("112837.06")


def test_split_that_sums_is_not_an_error():
    a = {
        "REC-1055": {
            "record_id": "REC-1055",
            "total_value": Decimal("179877.32"),
            "location_id": "LOC-103",
            "event_date": "2026-03-22",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4055",
            "record_ref": "REC-1055",
            "value": Decimal("71950.93"),
            "location_id": "LOC-103",
            "recorded_on": "2026-03-22",
        },
        {
            "entry_id": "ENT/2026/4056",
            "record_ref": "REC-1055",
            "value": Decimal("107926.39"),
            "location_id": "LOC-103",
            "recorded_on": "2026-03-22",
        },
    ]
    res = compare_ledgers(a, b)
    assert res == []


def test_value_mismatch():
    a = {
        "REC-1003": {
            "record_id": "REC-1003",
            "total_value": Decimal("121388.01"),
            "location_id": "LOC-101",
            "event_date": "2026-03-12",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4003",
            "record_ref": "REC-1003",
            "value": Decimal("94834.38"),
            "location_id": "LOC-101",
            "recorded_on": "2026-03-12",
        }
    ]
    res = compare_ledgers(a, b)
    assert len(res) == 1
    assert res[0]["reason"] == "VALUE_MISMATCH"
    assert res[0]["record_id"] == "REC-1003"
    assert res[0]["a_value"] == Decimal("121388.01")
    assert res[0]["b_value"] == Decimal("94834.38")
    assert res[0]["difference"] == Decimal("26553.63")


def test_blank_value_is_flagged_not_zero():
    a = {
        "REC-1050": {
            "record_id": "REC-1050",
            "total_value": Decimal("160405.85"),
            "location_id": "LOC-103",
            "event_date": "2026-03-25",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4050",
            "record_ref": "REC-1050",
            "value": None,
            "location_id": "LOC-103",
            "recorded_on": "2026-03-25",
        }
    ]
    res = compare_ledgers(a, b)
    assert len(res) == 1
    assert res[0]["reason"] == "VALUE_MISMATCH"
    assert res[0]["record_id"] == "REC-1050"
    assert res[0]["a_value"] == Decimal("160405.85")
    assert res[0]["b_value"] is None
    assert res[0]["difference"] is None


def test_location_mismatch():
    a = {
        "REC-1077": {
            "record_id": "REC-1077",
            "total_value": Decimal("1000.00"),
            "location_id": "LOC-102",
            "event_date": "2026-03-20",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4077",
            "record_ref": "REC-1077",
            "value": Decimal("1000.00"),
            "location_id": "LOC-201",
            "recorded_on": "2026-03-20",
        }
    ]
    res = compare_ledgers(a, b, include_extra_checks=True)
    assert len(res) == 1
    assert res[0]["reason"] == "LOCATION_MISMATCH"
    assert res[0]["a_location"] == "LOC-102"
    assert res[0]["b_location"] == "LOC-201"


def test_date_mismatch():
    a = {
        "REC-1009": {
            "record_id": "REC-1009",
            "total_value": Decimal("500.00"),
            "location_id": "LOC-101",
            "event_date": "2026-03-31",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4009",
            "record_ref": "REC-1009",
            "value": Decimal("500.00"),
            "location_id": "LOC-101",
            "recorded_on": "2026-04-02",
        }
    ]
    res = compare_ledgers(a, b, include_extra_checks=True)
    assert len(res) == 1
    assert res[0]["reason"] == "DATE_MISMATCH"
    assert res[0]["record_id"] == "REC-1009"


def test_clean_matching_row_produces_no_disagreement():
    a = {
        "REC-1001": {
            "record_id": "REC-1001",
            "total_value": Decimal("50000.00"),
            "location_id": "LOC-101",
            "event_date": "2026-03-10",
            "state": "CONFIRMED",
        }
    }
    b = [
        {
            "entry_id": "ENT/2026/4001",
            "record_ref": "REC-1001",
            "value": Decimal("50000.00"),
            "location_id": "LOC-101",
            "recorded_on": "2026-03-10",
        }
    ]
    res = compare_ledgers(a, b, include_extra_checks=True)
    assert res == []


def test_messy_references_normalized_match_cleanly():
    raw_refs = ["rec1034", " REC - 1070 ", "1112"]
    for raw in raw_refs:
        cleaned = normalize_ref(raw)
        a = {
            cleaned: {
                "record_id": cleaned,
                "total_value": Decimal("25000.00"),
                "location_id": "LOC-101",
                "event_date": "2026-03-15",
                "state": "CONFIRMED",
            }
        }
        b = [
            {
                "entry_id": f"ENT-{cleaned}",
                "record_ref": cleaned,
                "value": Decimal("25000.00"),
                "location_id": "LOC-101",
                "recorded_on": "2026-03-15",
            }
        ]
        res = compare_ledgers(a, b, include_extra_checks=True)
        assert res == []
