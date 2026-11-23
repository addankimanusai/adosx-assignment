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
