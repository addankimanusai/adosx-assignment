from decimal import Decimal
import pytest
from reconcile.compare import compare_ledgers


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

